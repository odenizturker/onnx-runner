#include <iostream>
#include <string>
#include <vector>
#include <filesystem>
#include <chrono>
#include <random>
#include <onnxruntime_cxx_api.h>

namespace fs = std::filesystem;

// Real ONNX Runtime inference
void run_onnx_inference(const std::string& model_path) {
    Ort::Env env(ORT_LOGGING_LEVEL_WARNING, "ONNXInference");
    Ort::SessionOptions session_options;
    session_options.SetIntraOpNumThreads(1);

    Ort::Session session(env, model_path.c_str(), session_options);

    // Get input/output info
    Ort::AllocatorWithDefaultOptions allocator;
    size_t num_input_nodes = session.GetInputCount();
    size_t num_output_nodes = session.GetOutputCount();

    if (num_input_nodes == 0) {
        std::cerr << "Warning: No input nodes found in model\n";
        return;
    }

    // Get input shape
    auto input_name = session.GetInputNameAllocated(0, allocator);
    auto input_type_info = session.GetInputTypeInfo(0);
    auto tensor_info = input_type_info.GetTensorTypeAndShapeInfo();
    std::vector<int64_t> input_shape = tensor_info.GetShape();

    // Calculate input size
    size_t input_tensor_size = 1;
    for (auto dim : input_shape) {
        if (dim < 0) dim = 1; // Handle dynamic dimensions
        input_tensor_size *= dim;
    }

    // Prepare input tensor with random values
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_real_distribution<float> dis(0.0f, 1.0f);

    std::vector<float> input_tensor_values(input_tensor_size);
    for (size_t i = 0; i < input_tensor_size; ++i) {
        input_tensor_values[i] = dis(gen);
    }

    std::vector<const char*> input_names = {input_name.get()};
    std::vector<const char*> output_names;

    for (size_t i = 0; i < num_output_nodes; i++) {
        auto name = session.GetOutputNameAllocated(i, allocator);
        output_names.push_back(name.get());
    }

    Ort::MemoryInfo memory_info = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    Ort::Value input_tensor = Ort::Value::CreateTensor<float>(
        memory_info, input_tensor_values.data(), input_tensor_size,
        input_shape.data(), input_shape.size());

    // Run inference
    auto output_tensors = session.Run(
        Ort::RunOptions{nullptr},
        input_names.data(), &input_tensor, 1,
        output_names.data(), num_output_nodes);
}

int main(int argc, char** argv) {
    if (argc != 3) {
        std::cerr << "Usage: ./onnx_runner <onnx_filename> <duration_seconds>\n";
        return 1;
    }

    std::string model_filename = argv[1];
    int duration_seconds = std::atoi(argv[2]);

    if (duration_seconds <= 0) {
        std::cerr << "Error: Duration must be positive integer\n";
        return 1;
    }

    // Always look for model in /data/local/tmp/models (running on Android device)
    fs::path model_path = fs::path("/data/local/tmp/models") / model_filename;

    if (!fs::exists(model_path)) {
        std::cerr << "Error: Model file not found at '" << model_path.string() << "'\n";
        return 1;
    }

    using clock = std::chrono::steady_clock;
    uint64_t iterations = 0;

    auto start = clock::now();
    auto deadline = start + std::chrono::seconds(duration_seconds);

    // Run inference until deadline
    while (clock::now() < deadline) {
        try {
            run_onnx_inference(model_path.string());
            ++iterations;
        } catch (const Ort::Exception& e) {
            std::cerr << "ONNX Runtime error: " << e.what() << "\n";
            return -1;
        }
    }

    auto end = clock::now();
    auto elapsed_ms = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();

    // Output results
    std::cout << "=== Benchmark Results ===\n";
    std::cout << "Model: " << model_filename << "\n";
    std::cout << "Duration: " << duration_seconds << "s\n";
    std::cout << "Iterations: " << iterations << "\n";
    std::cout << "Elapsed (ms): " << elapsed_ms << "\n";

    double throughput = static_cast<double>(iterations) * 1000.0 / static_cast<double>(elapsed_ms);
    std::cout << "Throughput: " << throughput << " inf/s\n";

    return 0;
}

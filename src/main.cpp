#include <iostream>
#include <string>
#include <vector>
#include <filesystem>
#include <chrono>
#include <thread>
#include <random>
#include <cstdlib>
#include <onnxruntime_cxx_api.h>
#include "onnxruntime_c_api.h"

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

    // Prepare random number generator
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_real_distribution<float> dis(0.0f, 1.0f);

    // Prepare all inputs
    std::vector<Ort::AllocatedStringPtr> input_name_ptrs;
    std::vector<const char*> input_names;
    std::vector<std::vector<float>> input_data_storage;
    std::vector<std::vector<int64_t>> input_shapes;
    std::vector<Ort::Value> input_tensors;

    Ort::MemoryInfo memory_info = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);

    for (size_t i = 0; i < num_input_nodes; ++i) {
        // Get input name and shape
        input_name_ptrs.push_back(session.GetInputNameAllocated(i, allocator));
        input_names.push_back(input_name_ptrs.back().get());

        auto input_type_info = session.GetInputTypeInfo(i);
        auto tensor_info = input_type_info.GetTensorTypeAndShapeInfo();
        std::vector<int64_t> input_shape = tensor_info.GetShape();

        // Calculate input size
        size_t input_tensor_size = 1;
        for (auto dim : input_shape) {
            if (dim < 0) dim = 1; // Handle dynamic dimensions
            input_tensor_size *= dim;
        }

        // Create random input data
        std::vector<float> input_tensor_values(input_tensor_size);
        for (size_t j = 0; j < input_tensor_size; ++j) {
            input_tensor_values[j] = dis(gen);
        }

        // Store data and shape
        input_data_storage.push_back(std::move(input_tensor_values));
        input_shapes.push_back(input_shape);

        // Create tensor
        input_tensors.push_back(Ort::Value::CreateTensor<float>(
            memory_info,
            input_data_storage.back().data(),
            input_tensor_size,
            input_shapes.back().data(),
            input_shapes.back().size()));
    }

    // Store output names properly to avoid memory issues
    std::vector<Ort::AllocatedStringPtr> output_name_ptrs;
    std::vector<const char*> output_names;

    for (size_t i = 0; i < num_output_nodes; i++) {
        output_name_ptrs.push_back(session.GetOutputNameAllocated(i, allocator));
        output_names.push_back(output_name_ptrs.back().get());
    }

    // Run inference
    auto output_tensors = session.Run(
        Ort::RunOptions{nullptr},
        input_names.data(), input_tensors.data(), num_input_nodes,
        output_names.data(), num_output_nodes);
}

int main(int argc, char** argv) {
    if (argc != 5) {
        std::cerr << "Usage: ./onnx_runner <onnx_filename> <warmup_seconds> <silence_seconds> <measurement_seconds>\n";
        return 1;
    }

    std::string model_filename = argv[1];
    int warmup_seconds = std::atoi(argv[2]);
    int silence_seconds = std::atoi(argv[3]);
    int measurement_seconds = std::atoi(argv[4]);

    if (warmup_seconds < 0 || silence_seconds < 0 || measurement_seconds <= 0) {
        std::cerr << "Error: Durations must be non-negative (measurement must be positive)\n";
        return 1;
    }

    // Always look for model in /data/local/tmp/models (running on Android device)
    fs::path model_path = fs::path("/data/local/tmp/models") / model_filename;

    if (!fs::exists(model_path)) {
        std::cerr << "Error: Model file not found at '" << model_path.string() << "'\n";
        return 1;
    }

    using clock = std::chrono::steady_clock;

    std::cout << "=== Starting 3-Phase Benchmark ===\n";
    std::cout << "Model: " << model_filename << "\n";
    std::cout << "Phase 1 (Warmup): " << warmup_seconds << "s\n";
    std::cout << "Phase 2 (Silence): " << silence_seconds << "s\n";
    std::cout << "Phase 3 (Measurement): " << measurement_seconds << "s\n";
    std::cout << "===================================\n\n";

    // Phase 1: Warmup
    if (warmup_seconds > 0) {
        std::cout << "[Phase 1/3] Warmup (" << warmup_seconds << "s)...\n";
        uint64_t warmup_iterations = 0;
        auto start = clock::now();
        auto deadline = start + std::chrono::seconds(warmup_seconds);

        while (clock::now() < deadline) {
            try {
                run_onnx_inference(model_path.string());
                ++warmup_iterations;
            } catch (const Ort::Exception& e) {
                std::cerr << "ONNX Runtime error during warmup: " << e.what() << "\n";
                return -1;
            }
        }

        auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(clock::now() - start).count();
        std::cout << "  ✓ Warmup completed (" << warmup_iterations << " iterations, "
                  << elapsed << "ms)\n\n";
    }

    // Phase 2: Silence - just wait for system stabilization
    if (silence_seconds > 0) {
        std::cout << "[Phase 2/3] Silence (" << silence_seconds << "s)...\n";
        std::this_thread::sleep_for(std::chrono::seconds(silence_seconds));
        std::cout << "  ✓ Silence completed\n\n";
    }

    // Reset battery statistics before measurement
    std::cout << "[Phase 2.5/3] Resetting battery statistics...\n";
    int reset_result = system("dumpsys batterystats --reset > /dev/null 2>&1");
    if (reset_result == 0) {
        std::cout << "  ✓ Battery statistics reset\n\n";
    } else {
        std::cerr << "  ⚠ Warning: Failed to reset battery statistics (code: "
                  << reset_result << ")\n\n";
    }

    // Small delay to ensure stats are reset
    std::this_thread::sleep_for(std::chrono::milliseconds(500));

    // Phase 3: Measurement
    std::cout << "[Phase 3/3] Measurement (" << measurement_seconds << "s)...\n";
    uint64_t measurement_iterations = 0;
    auto measurement_start = clock::now();
    auto measurement_deadline = measurement_start + std::chrono::seconds(measurement_seconds);

    while (clock::now() < measurement_deadline) {
        try {
            run_onnx_inference(model_path.string());
            ++measurement_iterations;
        } catch (const Ort::Exception& e) {
            std::cerr << "ONNX Runtime error during measurement: " << e.what() << "\n";
            return -1;
        }
    }

    auto measurement_end = clock::now();
    auto measurement_elapsed_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        measurement_end - measurement_start).count();

    std::cout << "  ✓ Measurement completed\n\n";

    // Output final results
    std::cout << "=== Benchmark Results ===\n";
    std::cout << "Model: " << model_filename << "\n";
    std::cout << "Measurement Duration: " << measurement_seconds << "s\n";
    std::cout << "Iterations: " << measurement_iterations << "\n";
    std::cout << "Elapsed (ms): " << measurement_elapsed_ms << "\n";

    double throughput = static_cast<double>(measurement_iterations) * 1000.0 /
                      static_cast<double>(measurement_elapsed_ms);
    std::cout << "Throughput: " << throughput << " inf/s\n";

    return 0;
}

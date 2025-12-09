#include <iostream>
#include <string>
#include <vector>
#include <filesystem>
#include <chrono>
#include <thread>
#include <random>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <onnxruntime_cxx_api.h>
#include "onnxruntime_c_api.h"

namespace fs = std::filesystem;

// Configuration constants
namespace Config {
    // Paths
    constexpr const char *MODEL_BASE_PATH = "/data/local/tmp/models";
    constexpr const char *MEASUREMENTS_DIR = "/data/local/tmp/measurements";

    // ONNX Runtime settings
    constexpr int INTRA_OP_NUM_THREADS = 1;
    constexpr OrtLoggingLevel LOGGING_LEVEL = ORT_LOGGING_LEVEL_WARNING;
    constexpr const char *ENV_NAME = "ONNXInference";

    // Random data generation
    constexpr float RANDOM_MIN = 0.0f;
    constexpr float RANDOM_MAX = 1.0f;
    constexpr int64_t DEFAULT_DYNAMIC_DIM = 1;

    // Timing
    constexpr int STATS_RESET_DELAY_MS = 500;

    // CSV format
    constexpr const char *CSV_DELIMITER = ",";
    constexpr int FLOAT_PRECISION = 3;
}

// Get current timestamp in format: YYYYMMDD_HHMMSS
std::string get_current_timestamp() {
    auto now = std::chrono::system_clock::now();
    auto time_t_now = std::chrono::system_clock::to_time_t(now);
    std::tm tm_now{};

    if (localtime_r(&time_t_now, &tm_now) == nullptr) {
        std::cerr << "Warning: Failed to get local time, using epoch\n";
        return "19700101_000000";
    }

    std::ostringstream oss;
    oss << std::put_time(&tm_now, "%Y%m%d_%H%M%S");
    return oss.str();
}

// Helper function to sanitize filename
std::string sanitize_filename(const std::string &filename) {
    std::string sanitized = filename;
    std::replace(sanitized.begin(), sanitized.end(), '/', '_');
    std::replace(sanitized.begin(), sanitized.end(), '\\', '_');
    return sanitized;
}

// Export performance metrics to CSV file
bool export_performance_metrics_csv(
    const std::string &model_filename,
    const std::string &timestamp,
    uint64_t measurement_iterations,
    double measurement_elapsed_ms,
    double us_per_inference,
    double total_time_sec,
    uint64_t warmup_iterations,
    double warmup_elapsed_ms
) {
    const std::string safe_model_name = sanitize_filename(model_filename);
    const std::string output_file = std::string(Config::MEASUREMENTS_DIR) + "/" +
                                    safe_model_name + "_" + timestamp + "_performance.csv";

    std::ofstream file(output_file);
    if (!file.is_open()) {
        std::cerr << "Warning: Could not create performance metrics file: " << output_file << "\n";
        return false;
    }

    // Set precision for floating point numbers
    file << std::fixed << std::setprecision(Config::FLOAT_PRECISION);

    // Write CSV header
    file << "model" << Config::CSV_DELIMITER
            << "timestamp" << Config::CSV_DELIMITER
            << "measurement_iterations" << Config::CSV_DELIMITER
            << "measurement_elapsed_ms" << Config::CSV_DELIMITER
            << "us_per_inference" << Config::CSV_DELIMITER
            << "total_time_sec" << Config::CSV_DELIMITER
            << "warmup_iterations" << Config::CSV_DELIMITER
            << "warmup_elapsed_ms" << "\n";

    // Write data row
    file << model_filename << Config::CSV_DELIMITER
            << timestamp << Config::CSV_DELIMITER
            << measurement_iterations << Config::CSV_DELIMITER
            << measurement_elapsed_ms << Config::CSV_DELIMITER
            << us_per_inference << Config::CSV_DELIMITER
            << total_time_sec << Config::CSV_DELIMITER
            << warmup_iterations << Config::CSV_DELIMITER
            << warmup_elapsed_ms << "\n";

    file.close();

    if (file.fail()) {
        std::cerr << "Warning: Error writing to performance metrics file\n";
        return false;
    }

    std::cout << "  ℹ Performance metrics exported to: " << output_file << "\n";
    return true;
}

// Real ONNX Runtime inference
void run_onnx_inference(const std::string &model_path) {
    Ort::Env env(Config::LOGGING_LEVEL, Config::ENV_NAME);
    Ort::SessionOptions session_options;
    session_options.SetIntraOpNumThreads(Config::INTRA_OP_NUM_THREADS);

    Ort::Session session(env, model_path.c_str(), session_options);

    // Get input/output info
    Ort::AllocatorWithDefaultOptions allocator;
    const size_t num_input_nodes = session.GetInputCount();
    const size_t num_output_nodes = session.GetOutputCount();

    if (num_input_nodes == 0) {
        std::cerr << "Warning: No input nodes found in model\n";
        return;
    }

    // Prepare random number generator
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_real_distribution<float> dis(Config::RANDOM_MIN, Config::RANDOM_MAX);

    // Prepare all inputs
    std::vector<Ort::AllocatedStringPtr> input_name_ptrs;
    std::vector<const char *> input_names;
    std::vector<std::vector<float> > input_data_storage;
    std::vector<std::vector<int64_t> > input_shapes;
    std::vector<Ort::Value> input_tensors;

    Ort::MemoryInfo memory_info = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);

    for (size_t i = 0; i < num_input_nodes; ++i) {
        // Get input name and shape
        input_name_ptrs.push_back(session.GetInputNameAllocated(i, allocator));
        input_names.push_back(input_name_ptrs.back().get());

        auto input_type_info = session.GetInputTypeInfo(i);
        auto tensor_info = input_type_info.GetTensorTypeAndShapeInfo();
        std::vector<int64_t> input_shape = tensor_info.GetShape();

        // Calculate input size (handle dynamic dimensions)
        size_t input_tensor_size = 1;
        for (auto &dim: input_shape) {
            if (dim < 0) {
                dim = Config::DEFAULT_DYNAMIC_DIM;
            }
            input_tensor_size *= static_cast<size_t>(dim);
        }

        // Create random input data
        std::vector<float> input_tensor_values(input_tensor_size);
        for (auto &val: input_tensor_values) {
            val = dis(gen);
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
    std::vector<const char *> output_names;

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

int main(int argc, char **argv) {
    if (argc != 5) {
        std::cerr << "Usage: ./onnx_runner <onnx_filename> <warmup_seconds> <silence_seconds> <measurement_seconds>\n";
        return 1;
    }

    const std::string model_filename = argv[1];
    const int warmup_seconds = std::atoi(argv[2]);
    const int silence_seconds = std::atoi(argv[3]);
    const int measurement_seconds = std::atoi(argv[4]);

    if (warmup_seconds < 0 || silence_seconds < 0 || measurement_seconds <= 0) {
        std::cerr << "Error: Durations must be non-negative (measurement must be positive)\n";
        return 1;
    }

    // Build model path using Config constant
    const fs::path model_path = fs::path(Config::MODEL_BASE_PATH) / model_filename;

    if (!fs::exists(model_path)) {
        std::cerr << "Error: Model file not found at '" << model_path.string() << "'\n";
        return 1;
    }

    using clock = std::chrono::steady_clock;

    // Capture timestamp at the start
    const std::string timestamp = get_current_timestamp();

    std::cout << "=== Starting 3-Phase Benchmark ===\n";
    std::cout << "Model: " << model_filename << "\n";
    std::cout << "Timestamp: " << timestamp << "\n";
    std::cout << "Phase 1 (Warmup): " << warmup_seconds << "s\n";
    std::cout << "Phase 2 (Silence): " << silence_seconds << "s\n";
    std::cout << "Phase 3 (Measurement): " << measurement_seconds << "s\n";
    std::cout << "===================================\n\n";

    // Phase 1: Warmup
    uint64_t warmup_iterations = 0;
    double warmup_elapsed_ms = 0.0;

    if (warmup_seconds > 0) {
        std::cout << "[Phase 1/3] Warmup (" << warmup_seconds << "s)...\n";
        const auto start = clock::now();
        const auto deadline = start + std::chrono::seconds(warmup_seconds);

        while (clock::now() < deadline) {
            try {
                run_onnx_inference(model_path.string());
                ++warmup_iterations;
            } catch (const Ort::Exception &e) {
                std::cerr << "ONNX Runtime error during warmup: " << e.what() << "\n";
                return -1;
            }
        }

        const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
            clock::now() - start).count();
        warmup_elapsed_ms = static_cast<double>(elapsed);
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
    const int reset_result = system("dumpsys batterystats --reset > /dev/null 2>&1");
    if (reset_result == 0) {
        std::cout << "  ✓ Battery statistics reset\n\n";
    } else {
        std::cerr << "  ⚠ Warning: Failed to reset battery statistics (code: "
                << reset_result << ")\n\n";
    }

    // Small delay to ensure stats are reset
    std::this_thread::sleep_for(std::chrono::milliseconds(Config::STATS_RESET_DELAY_MS));

    // Phase 3: Measurement
    std::cout << "[Phase 3/3] Measurement (" << measurement_seconds << "s)...\n";
    uint64_t measurement_iterations = 0;
    const auto measurement_start = clock::now();
    const auto measurement_deadline = measurement_start + std::chrono::seconds(measurement_seconds);

    while (clock::now() < measurement_deadline) {
        try {
            run_onnx_inference(model_path.string());
            ++measurement_iterations;
        } catch (const Ort::Exception &e) {
            std::cerr << "ONNX Runtime error during measurement: " << e.what() << "\n";
            return -1;
        }
    }

    const auto measurement_end = clock::now();
    const auto measurement_elapsed_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        measurement_end - measurement_start).count();

    std::cout << "  ✓ Measurement completed\n\n";

    // Calculate metrics
    const double us_per_inference = (static_cast<double>(measurement_elapsed_ms) * 1000.0) /
                                    static_cast<double>(measurement_iterations);
    const double total_time_sec = static_cast<double>(measurement_elapsed_ms) / 1000.0;
    const double throughput = static_cast<double>(measurement_iterations) * 1000.0 /
                              static_cast<double>(measurement_elapsed_ms);

    // Output final results
    std::cout << "=== Benchmark Results ===\n";
    std::cout << "Model: " << model_filename << "\n";
    std::cout << "Timestamp: " << timestamp << "\n";
    std::cout << "Measurement Duration: " << measurement_seconds << "s\n";
    std::cout << "Iterations: " << measurement_iterations << "\n";
    std::cout << "Elapsed (ms): " << measurement_elapsed_ms << "\n";
    std::cout << "Microseconds per inference: " << std::fixed << std::setprecision(2)
            << us_per_inference << " µs\n";
    std::cout << "Throughput: " << std::fixed << std::setprecision(2)
            << throughput << " inf/s\n";
    std::cout << "=========================\n";

    // Create measurements directory if it doesn't exist
    const std::string mkdir_cmd = std::string("mkdir -p ") + Config::MEASUREMENTS_DIR;
    system(mkdir_cmd.c_str());

    // Export performance metrics to CSV file
    export_performance_metrics_csv(
        model_filename,
        timestamp,
        measurement_iterations,
        static_cast<double>(measurement_elapsed_ms),
        us_per_inference,
        total_time_sec,
        warmup_iterations,
        warmup_elapsed_ms
    );

    return 0;
}

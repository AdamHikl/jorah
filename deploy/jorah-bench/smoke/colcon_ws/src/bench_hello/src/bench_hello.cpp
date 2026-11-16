// Starts a node and stops it. Building it proves the toolchain; running it shows whether the
// middleware (DDS) can start where it runs, which bench-smoke.sh reports as information only.
#include <memory>

#include "rclcpp/rclcpp.hpp"

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<rclcpp::Node>("bench_hello");
  RCLCPP_INFO(node->get_logger(), "bench_hello: node started");
  rclcpp::shutdown();
  return 0;
}

cmake_minimum_required(VERSION 3.8)
project(bench_hello)

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)

add_executable(bench_hello src/bench_hello.cpp)
target_link_libraries(bench_hello rclcpp::rclcpp)
install(TARGETS bench_hello DESTINATION lib/${PROJECT_NAME})

ament_package()

cmake_minimum_required(VERSION 3.15)
project(analysis)

set(CMAKE_CXX_STANDARD 17)
add_subdirectory(./csvparser)
aux_source_directory(${CMAKE_SOURCE_DIR} SRCS)
aux_source_directory(${CMAKE_SOURCE_DIR}/storage STORAGE_SRCS)
add_executable(${PROJECT_NAME} ${SRCS} ${STORAGE_SRCS})

target_link_libraries(${PROJECT_NAME} -lpthread -lboost_thread -lrocksdb)
target_link_libraries(${PROJECT_NAME} csv_parser)

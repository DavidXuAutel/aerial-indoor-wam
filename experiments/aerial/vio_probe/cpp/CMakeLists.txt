cmake_minimum_required(VERSION 3.16)
project(ov_euroc_offline LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT DEFINED OPENVINS_ROOT)
  set(OPENVINS_ROOT "$ENV{HOME}/src/open_vins")
endif()
if(NOT DEFINED OPENVINS_BUILD)
  set(OPENVINS_BUILD "${OPENVINS_ROOT}/ov_msckf/build")
endif()

find_package(Eigen3 REQUIRED)
find_package(OpenCV REQUIRED)
find_package(Boost REQUIRED COMPONENTS system filesystem thread date_time)
find_package(Ceres REQUIRED)

function(add_ov_bin name src)
  add_executable(${name} ${src})
  target_include_directories(${name} PRIVATE
    ${OPENVINS_ROOT}/ov_msckf/src
    ${OPENVINS_ROOT}/ov_core/src
    ${OPENVINS_ROOT}/ov_init/src
    ${EIGEN3_INCLUDE_DIR}
    ${OpenCV_INCLUDE_DIRS}
    ${CERES_INCLUDE_DIRS}
  )
  target_link_libraries(${name} PRIVATE
    ${OPENVINS_BUILD}/libov_msckf_lib.so
    ${OpenCV_LIBRARIES}
    ${Boost_LIBRARIES}
    ${CERES_LIBRARIES}
  )
  set_target_properties(${name} PROPERTIES
    BUILD_RPATH "${OPENVINS_BUILD}"
    INSTALL_RPATH "${OPENVINS_BUILD}"
  )
endfunction()

add_ov_bin(ov_euroc_offline ov_euroc_offline.cpp)
add_ov_bin(ov_stream_online ov_stream_online.cpp)

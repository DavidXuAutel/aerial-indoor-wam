/**
 * Streaming OpenVINS for indoor closed-loop (ROS-free).
 *
 * Usage:
 *   ov_stream_online <config.yaml>
 *
 * Line protocol on stdin (one command per line); replies on stdout:
 *   HELLO                          → OK stream
 *   RESET                          → OK reset  (new VioManager)
 *   GTINIT t qx qy qz qw px py pz vx vy vz bgx bgy bgz bax bay baz
 *                                  → OK gtinit   (JPL quat x,y,z,w)
 *   IMU t wx wy wz ax ay az        → OK imu
 *   CAM t /abs/path.png            → OK cam [init=0|1]
 *   POSE                           → POSE t px py pz qx qy qz qw init=0|1 seeded=0|1
 *   QUIT                           → OK bye
 *
 * Errors: ERR <msg>
 */
#include <fstream>
#include <iostream>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

#include <Eigen/Eigen>
#include <opencv2/opencv.hpp>

#include "core/VioManager.h"
#include "core/VioManagerOptions.h"
#include "state/State.h"
#include "utils/print.h"
#include "utils/sensor_data.h"

static void reply_ok(const std::string &msg) {
  std::cout << "OK " << msg << std::endl;
  std::cout.flush();
}

static void reply_err(const std::string &msg) {
  std::cout << "ERR " << msg << std::endl;
  std::cout.flush();
}

int main(int argc, char **argv) {
  if (argc < 2) {
    std::cerr << "usage: " << argv[0] << " <config.yaml>\n";
    return 2;
  }
  const std::string config_path = argv[1];

  auto parser = std::make_shared<ov_core::YamlParser>(config_path);
  ov_msckf::VioManagerOptions params;
  params.print_and_load(parser);
  // Keep line protocol on stdout clean (client also skips non-OK/ERR/POSE).
  ov_core::Printer::setPrintLevel("ERROR");

  std::shared_ptr<ov_msckf::VioManager> vio =
      std::make_shared<ov_msckf::VioManager>(params);
  bool gt_seeded = false;

  auto recreate = [&]() {
    vio = std::make_shared<ov_msckf::VioManager>(params);
    gt_seeded = false;
  };

  reply_ok("stream");

  std::string line;
  while (std::getline(std::cin, line)) {
    if (line.empty()) continue;
    std::stringstream ss(line);
    std::string cmd;
    ss >> cmd;
    if (cmd == "HELLO") {
      reply_ok("stream");
    } else if (cmd == "RESET") {
      recreate();
      reply_ok("reset");
    } else if (cmd == "QUIT") {
      reply_ok("bye");
      break;
    } else if (cmd == "GTINIT") {
      Eigen::Matrix<double, 17, 1> imustate = Eigen::Matrix<double, 17, 1>::Zero();
      for (int i = 0; i < 17; ++i) {
        if (!(ss >> imustate(i, 0))) {
          reply_err("gtinit_parse");
          goto cont;
        }
      }
      vio->initialize_with_gt(imustate);
      gt_seeded = true;
      reply_ok("gtinit");
    } else if (cmd == "IMU") {
      ov_core::ImuData d;
      if (!(ss >> d.timestamp >> d.wm(0) >> d.wm(1) >> d.wm(2) >> d.am(0) >> d.am(1) >> d.am(2))) {
        reply_err("imu_parse");
        goto cont;
      }
      vio->feed_measurement_imu(d);
      reply_ok("imu");
    } else if (cmd == "CAM") {
      double t = 0.0;
      std::string path;
      if (!(ss >> t)) {
        reply_err("cam_parse_t");
        goto cont;
      }
      std::getline(ss, path);
      while (!path.empty() && (path.front() == ' ' || path.front() == '\t')) path.erase(path.begin());
      while (!path.empty() && (path.back() == '\r' || path.back() == ' ')) path.pop_back();
      cv::Mat img = cv::imread(path, cv::IMREAD_GRAYSCALE);
      if (img.empty()) {
        reply_err("cam_read " + path);
        goto cont;
      }
      ov_core::CameraData d;
      d.timestamp = t;
      d.sensor_ids = {0};
      d.images = {img};
      d.masks = {cv::Mat(img.size(), CV_8UC1, cv::Scalar(0))};
      vio->feed_measurement_camera(d);
      std::cout << "OK cam init=" << (vio->initialized() ? 1 : 0)
                << " seeded=" << (gt_seeded ? 1 : 0) << std::endl;
      std::cout.flush();
    } else if (cmd == "POSE") {
      if (!(gt_seeded || vio->initialized())) {
        reply_err("not_ready");
        goto cont;
      }
      auto state = vio->get_state();
      Eigen::Vector3d p = state->_imu->pos();
      Eigen::Matrix<double, 4, 1> q = state->_imu->quat(); // JPL x,y,z,w
      double t = state->_timestamp;
      std::cout.setf(std::ios::fixed);
      std::cout.precision(9);
      std::cout << "POSE " << t << " " << p(0) << " " << p(1) << " " << p(2) << " " << q(0)
                << " " << q(1) << " " << q(2) << " " << q(3) << " init="
                << (vio->initialized() ? 1 : 0) << " seeded=" << (gt_seeded ? 1 : 0)
                << std::endl;
      std::cout.flush();
    } else {
      reply_err("unknown_cmd " + cmd);
    }
  cont:;
  }
  return 0;
}

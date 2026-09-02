/**
 * ROS-free OpenVINS EuRoC offline runner for aerial-indoor-wam vio_probe.
 *
 * Usage:
 *   ov_euroc_offline <config.yaml> <euroc_root> <out_tum.txt> [--gt-init] [--imu-only]
 */
#include <algorithm>
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
#include "utils/dataset_reader.h"
#include "utils/sensor_data.h"

struct ImuSample {
  int64_t t_ns;
  Eigen::Vector3d wm;
  Eigen::Vector3d am;
};

struct CamSample {
  int64_t t_ns;
  std::string path;
};

static std::vector<ImuSample> load_imu(const std::string &csv) {
  std::ifstream f(csv);
  if (!f) throw std::runtime_error("cannot open " + csv);
  std::string line;
  std::getline(f, line);
  std::vector<ImuSample> out;
  while (std::getline(f, line)) {
    if (line.empty() || line[0] == '#') continue;
    std::stringstream ss(line);
    std::string t, wx, wy, wz, ax, ay, az;
    if (!std::getline(ss, t, ',')) continue;
    std::getline(ss, wx, ',');
    std::getline(ss, wy, ',');
    std::getline(ss, wz, ',');
    std::getline(ss, ax, ',');
    std::getline(ss, ay, ',');
    std::getline(ss, az, ',');
    auto strip_cr = [](std::string &s) {
      while (!s.empty() && (s.back() == '\r' || s.back() == ' ')) s.pop_back();
    };
    strip_cr(t);
    strip_cr(az);
    ImuSample s;
    s.t_ns = std::stoll(t);
    s.wm = Eigen::Vector3d(std::stod(wx), std::stod(wy), std::stod(wz));
    s.am = Eigen::Vector3d(std::stod(ax), std::stod(ay), std::stod(az));
    out.push_back(s);
  }
  return out;
}

static std::vector<CamSample> load_cam(const std::string &csv, const std::string &datadir) {
  std::ifstream f(csv);
  if (!f) throw std::runtime_error("cannot open " + csv);
  std::string line;
  std::getline(f, line);
  std::vector<CamSample> out;
  while (std::getline(f, line)) {
    if (line.empty() || line[0] == '#') continue;
    std::stringstream ss(line);
    std::string t, name;
    if (!std::getline(ss, t, ',')) continue;
    std::getline(ss, name, ',');
    while (!name.empty() && (name.front() == ' ' || name.front() == '\t')) name.erase(name.begin());
    while (!name.empty() && (name.back() == '\r' || name.back() == ' ' || name.back() == '\t'))
      name.pop_back();
    while (!t.empty() && (t.back() == '\r' || t.back() == ' ')) t.pop_back();
    CamSample s;
    s.t_ns = std::stoll(t);
    s.path = datadir + "/" + name;
    out.push_back(s);
  }
  return out;
}

int main(int argc, char **argv) {
  if (argc < 4) {
    std::cerr << "usage: " << argv[0]
              << " <config.yaml> <euroc_root> <out_tum.txt> [--gt-init] [--imu-only]\n";
    return 2;
  }
  const std::string config_path = argv[1];
  const std::string euroc_root = argv[2];
  const std::string out_tum = argv[3];
  bool gt_init = false;
  bool imu_only = false;
  for (int i = 4; i < argc; ++i) {
    if (std::string(argv[i]) == "--gt-init") gt_init = true;
    if (std::string(argv[i]) == "--imu-only") imu_only = true;
  }

  auto parser = std::make_shared<ov_core::YamlParser>(config_path);
  ov_msckf::VioManagerOptions params;
  params.print_and_load(parser);
  auto vio = std::make_shared<ov_msckf::VioManager>(params);

  auto imu = load_imu(euroc_root + "/mav0/imu0/data.csv");
  auto cam = load_cam(euroc_root + "/mav0/cam0/data.csv", euroc_root + "/mav0/cam0/data");
  if (imu.empty() || cam.empty()) {
    std::cerr << "empty imu (" << imu.size() << ") or cam (" << cam.size() << ")\n";
    return 3;
  }
  std::cerr << "[ov_euroc_offline] imu=" << imu.size() << " cam=" << cam.size()
            << " gt_init=" << (gt_init ? "yes" : "no")
            << " imu_only=" << (imu_only ? "yes" : "no") << "\n";

  std::map<double, Eigen::Matrix<double, 17, 1>> gt_states;
  if (gt_init) {
    const std::string gt_csv = euroc_root + "/mav0/state_groundtruth_estimate0/data.csv";
    ov_core::DatasetReader::load_gt_file(gt_csv, gt_states);
    std::cerr << "[ov_euroc_offline] loaded gt states=" << gt_states.size() << "\n";
  }

  std::ofstream fout(out_tum);
  if (!fout) {
    std::cerr << "cannot write " << out_tum << "\n";
    return 4;
  }
  fout.setf(std::ios::fixed);
  fout.precision(9);
  fout << "# timestamp tx ty tz qx qy qz qw  (OpenVINS JPL)\n";

  size_t i_imu = 0, i_cam = 0;
  size_t n_written = 0;
  bool was_init = false;
  bool gt_seeded = false;

  // Seed once from GT at first camera time; estimate accel bias so AirSim
  // |a|≈10.1 does not integrate as free-fall against gravity_mag.
  if (gt_init && !gt_states.empty() && !cam.empty()) {
    const double t0 = 1e-9 * static_cast<double>(cam[0].t_ns);
    Eigen::Matrix<double, 17, 1> imustate;
    if (ov_core::DatasetReader::get_gt_state(t0, imustate, gt_states)) {
      Eigen::Vector3d a_mean = Eigen::Vector3d::Zero();
      size_t n_a = 0;
      for (size_t k = 0; k < imu.size() && n_a < 400; ++k) {
        a_mean += imu[k].am;
        ++n_a;
      }
      if (n_a > 0) {
        a_mean /= static_cast<double>(n_a);
        // Level assumption: want a_hat - ba ≈ [0,0,g] in body when aligned.
        const double g = params.gravity_mag;
        Eigen::Vector3d ba = a_mean - Eigen::Vector3d(0.0, 0.0, g);
        imustate(14, 0) = ba(0);
        imustate(15, 0) = ba(1);
        imustate(16, 0) = ba(2);
        std::cerr << "[ov_euroc_offline] seeded ba=" << ba.transpose()
                  << " from a_mean=" << a_mean.transpose() << " g=" << g << "\n";
      }
      // Thrifty: zero GT velocity — fixture vel is noisy / frame-mixed and
      // integrates to km-scale error on ZOH AirSim IMU.
      imustate(8, 0) = 0.0;
      imustate(9, 0) = 0.0;
      imustate(10, 0) = 0.0;
      vio->initialize_with_gt(imustate);
      gt_seeded = true;
      std::cerr << "[ov_euroc_offline] gt-init once at t=" << t0 << "\n";
    } else {
      std::cerr << "[ov_euroc_offline] gt-init failed at t0=" << t0 << "\n";
    }
  }

  auto write_pose = [&](double tstamp) {
    if (!(vio->initialized() || gt_seeded)) return;
    auto state = vio->get_state();
    Eigen::Vector3d p = state->_imu->pos();
    Eigen::Matrix<double, 4, 1> q = state->_imu->quat();
    fout << tstamp << " " << p(0) << " " << p(1) << " " << p(2) << " " << q(0) << " "
         << q(1) << " " << q(2) << " " << q(3) << "\n";
    ++n_written;
    was_init = true;
  };

  while (i_imu < imu.size() || i_cam < cam.size()) {
    const bool prefer_imu =
        i_cam >= cam.size() || (i_imu < imu.size() && imu[i_imu].t_ns <= cam[i_cam].t_ns);
    if (prefer_imu) {
      ov_core::ImuData d;
      d.timestamp = 1e-9 * static_cast<double>(imu[i_imu].t_ns);
      d.wm = imu[i_imu].wm;
      d.am = imu[i_imu].am;
      vio->feed_measurement_imu(d);
      ++i_imu;
    } else {
      const double tstamp = 1e-9 * static_cast<double>(cam[i_cam].t_ns);
      cv::Mat img;
      if (imu_only) {
        // Still tick the camera rate so OpenVINS propagates IMU; blank → no features.
        img = cv::Mat(480, 640, CV_8UC1, cv::Scalar(0));
      } else {
        img = cv::imread(cam[i_cam].path, cv::IMREAD_GRAYSCALE);
        if (img.empty()) {
          std::cerr << "failed to read " << cam[i_cam].path << "\n";
          ++i_cam;
          continue;
        }
      }
      ov_core::CameraData d;
      d.timestamp = tstamp;
      d.sensor_ids = {0};
      d.images = {img};
      d.masks = {cv::Mat(img.size(), CV_8UC1, cv::Scalar(imu_only ? 255 : 0))};
      vio->feed_measurement_camera(d);
      ++i_cam;
      if (!was_init && vio->initialized()) {
        std::cerr << "[ov_euroc_offline] initialized() true at t=" << tstamp << "s\n";
      }
      write_pose(tstamp);
    }
  }

  std::cerr << "[ov_euroc_offline] wrote " << n_written << " poses -> " << out_tum
            << " initialized=" << (was_init ? "yes" : "no") << "\n";
  return (n_written > 0 && was_init) ? 0 : 5;
}

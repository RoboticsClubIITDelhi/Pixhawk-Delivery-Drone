# Robotics Summer Project 2025-26

<div align="center">
  <img src="https://img.shields.io/badge/Status-In%20Development-yellow" alt="Status: In Development">
  <img src="https://img.shields.io/badge/Team-Robotics%20Club-blue" alt="Team: Robotics Club">
  <img src=https://img.shields.io/badge/Platform-PX4-blue) alt="Platform: PX4">
  <div align="center">
    <img src="./photos/pixhawk.jpg" width="600" alt="Project Image">
    <br>
   
  </div>
</div>

## 🤖 Project Overview

The aim of this project is to simulate and create a pixhawk based delivery drone which can carry a parcel from one location to another, first manually using remote control, and then autonomously. A rigorous simulation on a model similar to the actual drone will be carried on Gazebo using the PX4 firmware, to test the drone's efficiency in every possible scenario and ensure that the drone, as well as the parcel, remain safe in most of the cases.

### 🎯 Goals

- ✅ Assemble and control the drone without GPS and telemetery
- ✅ Simulate the default iris quadcoptor on Gazebo
- ✅ Import a custom drone model in the PX4 environment
- 🟡 Simulate the custom drone on gazebo
- 🟡 Test the gripper in the simulation
- 🟡 Modify basic parameters like thrust, mass, gravity etc. to account for all eventualities
- 🟡 Add the gripper to the pixhawk quadcopter and fly the quadcopter with a payload (parcel)
- 🟡 Automate the entire process


## Firmware Installation and Setup
!ToDo()

## Hardware Setup and Calibration

The softwares needed to setup the hardware are :
- Qground Control/Mission Planner as ground station (in our case it is Qground Control)
- Ardupilot/PX4 firmware

We follow [Qground control installation](https://docs.qgroundcontrol.com/master/en/qgc-user-guide/getting_started/download_and_install.html) for installation of ground station.

Then we installed the PX4 firmware in pixhawk from firmware install section of Qground control.

After which, we have to change the default parameters so that we can disable the telemetry and GPS:
1. Disable GPS Usage and GPS Failsafe
	-	Disable GPS Hardware Detection:
	  -	Set `SYS_HAS_GPS` to `0` to indicate there is no GPS module.
	-	Disable GPS Aiding in EKF:
	  -	Set `EKF2_AID_MASK` to `3` (use only vision and barometer, no GPS).
	-	Allow Arming Without GPS:
	  -	Set `COM_ARM_WO_GPS` to `1` (allows arming without GPS).
	-	Position Loss Failsafe:
	  -	Set `COM_POSCTL_NAVL` to `0` (if using RC), so the drone switches to Altitude/Stabilized mode upon position loss, not failsafe.
	-	Optional: For some setups, you may also need to set circuit breakers:
	  -	`CBRK_GPSFAIL` to `240024` (disables GPS failsafe).
2. Disable Telemetry
	-	Disable MAVLink Telemetry Ports:
	  -	Set `MAV_0_CONFIG`, `MAV_1_CONFIG`, and `MAV_2_CONFIG` to `Disabled` (prevents PX4 from expecting telemetry hardware).
	-	Disable Data Link Loss Failsafe:
	  -	Set `NAV_DLL_ACT` to `Disabled` (no action if telemetry link is lost).
3. Disable Battery Failsafe
	-	Disable Battery Level Failsafes:
	  -	Set `COM_LOW_BAT_ACT` to `0` (no action on low battery).
	  -	Set `BAT_LOW_THR`, `BAT_CRIT_THR`, and `BAT_EMERGEN_THR` to `0` (disables battery warning, failsafe, and emergency actions).
  -	Disable Minimum Battery for Arming:
	  -	Set `COM_ARM_BAT_MIN` to `0` (allows arming with any battery level).
   
Next, there is settings for mode(inside the flight mode section):
- we set the mode to channel 5, such that
  - when the position is up, its in stabilized mode.
  - when the position is middle, its in Alt hold mode.
  - when the position is low, its in the land mode.
 
- Also we set the radio failsafe to land mode
  - Set `NAV_RCL_ACT` to `2` (corresponds to land mode).
 
And finally the calibrations (you will get the option on vehicle setup->left sidebar:
1. Accelerometer calibration
2. Gyroscope calibration
3. Compass calibration
4. Radio/RC calibration
5. ESC calibration


## ⏱️ Project Timeline
Main idea is to build a very very basic version first, probably within 2 weeks and then work on modifying it, (believer me doing otherwise is stupidity...)

### Week 1: Introduction
- Review the competition rulebook
-  Be familiar with github
-  Brainstorm ideas and design concepts based in the video,
-  Prepare Bill of Materials
-  Draft electronic system diagram
-  !TODO()


### Week 2: Hardware Assembly
-  Assemble mechanical components
- !TODO()

### Week 3: Debugging
-  Hardware and software troubleshooting
-  !TODO()

### Week 4: Algorithm Refinement
-  Enhance hardware robustness
-  !TODO()

### Weeks 5-7: Progressive Enhancements
- 🔄 Implement iterative improvements (tbd)
- !TODO()

## 📚 Resources

### Tools and References (tbd)
- !TODO()

### Development Software
- !TODO()



## 🤝 Contributor Notes
- We follow the [standard Git workflow](https://www.geeksforgeeks.org/git-workflows-with-open-source-collaboration/) for collaboration
- Suggestions for improvement are welcome via **Issues** or Discussions.

---


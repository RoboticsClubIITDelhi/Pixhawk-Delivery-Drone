import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from px4_msgs.msg import OffboardControlMode, TrajectorySetpoint, VehicleCommand
import numpy as np

class TeleopVelocityNode(Node):
    def __init__(self):
        super().__init__('teleop_velocity_node')

        self.cmd_vel = Twist()
        self.armed = False
        self.offboard_started = False

        self.vel_sub = self.create_subscription(Twist, '/cmd_vel', self.cmd_callback, 10)
        self.setpoint_pub = self.create_publisher(TrajectorySetpoint, '/fmu/in/trajectory_setpoint', 10)
        self.mode_pub = self.create_publisher(OffboardControlMode, '/fmu/in/offboard_control_mode', 10)
        self.command_pub = self.create_publisher(VehicleCommand, '/fmu/in/vehicle_command', 10)

        timer_period = 0.05  # 20 Hz
        self.timer = self.create_timer(timer_period, self.timer_callback)

    def cmd_callback(self, msg):
        self.cmd_vel = msg
        self.get_logger().info(
            f"Received /cmd_vel: "
            f"x={msg.linear.x}, y={msg.linear.y}, z={msg.linear.z}, yaw={msg.angular.z}"
        )

    def timer_callback(self):
        now = self.get_clock().now().nanoseconds // 1000

        # 1. Send OffboardControlMode
        mode_msg = OffboardControlMode()
        mode_msg.timestamp = now
        mode_msg.position = False
        mode_msg.velocity = True
        self.mode_pub.publish(mode_msg)

        # 2. Send TrajectorySetpoint (velocity only)
        sp_msg = TrajectorySetpoint()
        sp_msg.timestamp = now
        sp_msg.position = [np.nan, np.nan, np.nan]  # disables position control
        sp_msg.velocity = [
            float(self.cmd_vel.linear.x),
            float(self.cmd_vel.linear.y),
            -float(self.cmd_vel.linear.z)  # Z is inverted for NED
        ]
        sp_msg.yaw = float(self.cmd_vel.angular.z)
        self.setpoint_pub.publish(sp_msg)

        self.get_logger().info(f"Sent velocity setpoint: {sp_msg.velocity}")

        # 3. Send once: switch to OFFBOARD
        if not self.offboard_started:
            self.send_vehicle_command(92, 1.0)  # PX4_CMD_DO_SET_MODE, param1 = 1 (OFFBOARD)
            self.get_logger().info("Sent command to enter OFFBOARD mode")
            self.offboard_started = True

        # 4. Send once: ARM
        if not self.armed:
            self.send_vehicle_command(400, 1.0)  # PX4_CMD_COMPONENT_ARM_DISARM, param1 = 1 (ARM)
            self.get_logger().info("Sent ARM command")
            self.armed = True

    def send_vehicle_command(self, command, param1):
        cmd = VehicleCommand()
        cmd.timestamp = self.get_clock().now().nanoseconds // 1000
        cmd.param1 = param1
        cmd.command = command
        cmd.target_system = 1
        cmd.target_component = 1
        cmd.source_system = 1
        cmd.source_component = 1
        cmd.from_external = True
        self.command_pub.publish(cmd)

def main(args=None):
    rclpy.init(args=args)
    node = TeleopVelocityNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


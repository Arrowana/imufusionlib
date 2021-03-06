#/usr/bin/env python
import rospy
from robot.msg import *
from sensor_msgs.msg import Imu
from intf.msg import *

import math as m
from tf.transformations import euler_from_quaternion

speed_treshold=220
spot_turn_speed=80
wait_time=30.

def toDegrees(angle_rad):
	return 180.*angle_rad/m.pi

def normalizeAngle(angle):
	angle=angle % 360
	angle=(angle+360) % 360
	if(angle>180):
		angle-=360
	return angle

class Driver:
	def __init__(self):
		rospy.init_node('driving_straight')
		
		self.heading_goal=0.		

		self.wheel_radius=0.105
		self.tractor_axle_width=0.26
		self.K1=5.

		self.lastTime=rospy.Time.now()
		self.startWaitTime=rospy.Time.now()			

		self.state="straight"

		print "Variables ready"
		
		rospy.Subscriber('imu', Imu , self.imuCallback)
		self.velocity_pub = rospy.Publisher('msg_teleops', PlatformCmd, queue_size=10)

		print "Driver initialized"

		rospy.spin()

	def imuCallback(self, imu_msg):
		print "====="
		quaternion=(
			imu_msg.orientation.x, 
			imu_msg.orientation.y, 
			imu_msg.orientation.z,
			imu_msg.orientation.w)
		roll, pitch, yaw,=euler_from_quaternion(quaternion)
		print "yaw_deg", toDegrees(yaw)
		
		self.control(yaw)
		
	def control(self, yaw):
		currentTime=rospy.Time.now()
		elapsedSecs=(currentTime-self.lastTime).to_sec()
		
		print "elapsed secs:", elapsedSecs
		if elapsedSecs>wait_time:
			if self.state=="straight":
				self.state="spot_turn"
				if self.heading_goal==0.:
					self.heading_goal+=180.
				else:
					self.heading_goal-=180.

		if (self.state=="spot_turn" or "endSpotTurn") and abs(normalizeAngle(toDegrees(yaw)-self.heading_goal))<1.5:
			wait_secs=(currentTime-self.startWaitTime).to_sec()
			print "wait_secs:", wait_secs			
		
			if self.state=="spot_turn":
				self.state="endSpotTurn"
				self.startWaitTime=rospy.Time.now()
			elif  wait_secs>4. and self.state=="endSpotTurn":
				self.state="straight"
				self.lastTime=rospy.Time.now()
		
		print "state:", self.state
		if self.state=="straight":
			self.stabilize(yaw, 1.)
		elif self.state=="spot_turn":
			self.stabilize(yaw, 0.)

	def stabilize(self, yaw, u1r):
		print "heading_goal", self.heading_goal
		heading_err=yaw - m.pi*self.heading_goal/180
		print "heading_err_deg:", toDegrees(heading_err)

		# Keep heading_err within -180;180
		heading_err=m.pi*normalizeAngle(toDegrees(heading_err))/180.

		print "heading_err corr:", toDegrees(heading_err)
		if abs(toDegrees(heading_err))<20.:
			print "Normal"

			u2r=-self.K1*m.sin(heading_err)
			print "u2r:", u2r
			#Stabilize heading
			factor=20.
			left_speed=factor*(1./self.wheel_radius)*(u1r-self.tractor_axle_width*u2r)
			right_speed=factor*(1./self.wheel_radius)*(u1r+self.tractor_axle_width*u2r)

		elif abs(toDegrees(heading_err))>=20.:
			print "modify heading err because too large"
			sign=m.copysign(1, heading_err)

			left_speed=sign*spot_turn_speed
			right_speed=-sign*spot_turn_speed

		print "left_speed", left_speed
		print "right_speed", right_speed


		if left_speed > speed_treshold or right_speed > speed_treshold:
			print "speed_treshold reached"
			left_speed=0
			right_speed=0

		self.publish_velocities(int(left_speed), int(right_speed))

	def publish_velocities(self, left_motor_speed, right_motor_speed):
		platform_cmd_msg=PlatformCmd()
		platform_cmd_msg.command = 11

		platform_cmd_msg.params=[0,0]
		platform_cmd_msg.params[0] = left_motor_speed
		platform_cmd_msg.params[1] = right_motor_speed

		self.velocity_pub.publish(platform_cmd_msg)

if __name__ == '__main__':
	driver=Driver()

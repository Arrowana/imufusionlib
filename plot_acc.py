#!/usr/bin/env python
import rospy

import serial

from geometry_msgs.msg import Quaternion
from sensor_msgs.msg import Imu
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import random
from threading import Thread, Event
import time
import math as m

from tf.transformations import quaternion_from_euler

SERIALPORT="/dev/ttyUSB0"

class DataContainer(Thread):
    def __init__(self, lines):
        Thread.__init__(self)
        
        maxData=0
        self.ser = serial.Serial(SERIALPORT, 115200)
        self.data_dict={}
        self.lines=lines

        self.calibrated=False

        self.s_acc=1
        self.s_gyro=131*180/m.pi # sensivity+ deg to rad
        self.N_sample=10
        self.alpha=0.98 #tau/(tau+dt)

        self.imu_raw_pub = rospy.Publisher('imu_raw', Imu, queue_size=10)
        self.imu_filtered_pub = rospy.Publisher('imu_filtered', Imu, queue_size=10)

    def modify(self, line, data_name):
        #Plot only N_values
        length=40

        if(len(self.data_dict[data_name])>length):
            line.set_data(range(length),self.data_dict[data_name][-length:])
            line.axes.set_xlim(0, length)
            y_max=max([abs(x) for x in self.data_dict[data_name]])
            line.axes.set_ylim(-y_max, y_max)

    def update(self, frameNum):
        for line in self.lines:
            data_name=line.get_label()
            if data_name in self.data_dict:
                self.modify(line, data_name)

    def run(self):   
        for i in range(100000):
            print("Data received")
            data_raw=self.ser.readline()
            print(data_raw)
            data=data_raw.decode("utf-8")
            self.process(str(data))
            
            #time.sleep(1)

    def process(self, data):
        if "data:" in data:
            try:
                header, data_name=data.split(":")
                data_name,=data_name.splitlines()
                # Read value associated to data_name
                value_raw=self.ser.readline()
                #print(value_raw)
                value=float(value_raw.decode("utf-8"))
            except:
                print("Unexpected format of data")
                return

            # Store in dictionnary and add key if doesn't exist
            if data_name in self.data_dict:
                self.data_dict[data_name].append(value)
            else:
                self.data_dict[data_name]=[value]

            if "AcX" in self.data_dict:
                self.compute()

    def publish_ros(self):
        imu_msg=Imu()
        imu_msg.header.stamp=rospy.Time.now()
        imu_msg.header.frame_id="map"
        quat=quaternion_from_euler(-self.data_dict["acc_roll"][-1], self.data_dict["acc_pitch"][-1],self.data_dict["gyro_yaw"][-1])
        imu_msg.orientation.x=quat[0]
        imu_msg.orientation.y=quat[1]
        imu_msg.orientation.z=quat[2]
        imu_msg.orientation.w=quat[3]

        self.imu_raw_pub.publish(imu_msg)

        quat=quaternion_from_euler(-self.data_dict["roll"][-1], self.data_dict["pitch"][-1],self.data_dict["gyro_yaw"][-1])
        imu_msg.orientation.x=quat[0]
        imu_msg.orientation.y=quat[1]
        imu_msg.orientation.z=quat[2]
        imu_msg.orientation.w=quat[3]

        self.imu_filtered_pub.publish(imu_msg)
            
    def compute(self):
        if self.calibrated==False and len(self.data_dict["AcX"])>self.N_sample+1:
            self.calibrate()

            self.data_dict["acc_pitch"]=[]
            self.data_dict["acc_roll"]=[]

            self.data_dict["gyro_roll"]=[0]
            self.data_dict["gyro_pitch"]=[0]
            self.data_dict["gyro_yaw"]=[0]

            self.data_dict["roll"]=[0]
            self.data_dict["pitch"]=[0]

        if self.calibrated==True:
            dt=0.02

            print("COMPUTING--------------------------------")
            
            acc_x=(self.data_dict["AcX"][-1]-self.acc_x_cal)/self.s_acc
            acc_y=(self.data_dict["AcY"][-1]-self.acc_y_cal)/self.s_acc
            acc_z=(self.data_dict["AcZ"][-1]-self.acc_z_cal)/self.s_acc
            
            gyro_x=(self.data_dict["GyX"][-1]-self.gyro_x_cal)/self.s_gyro
            gyro_y=(self.data_dict["GyY"][-1]-self.gyro_y_cal)/self.s_gyro
            gyro_z=(self.data_dict["GyZ"][-1]-self.gyro_z_cal)/self.s_gyro
            

            # Roll and pitch from accelerometer
            acc_roll=m.atan2(acc_y, acc_z)
            self.data_dict["acc_roll"].append(acc_roll)

            acc_pitch=-m.atan2(acc_x,acc_z)
            self.data_dict["acc_pitch"].append(acc_pitch)

            # Roll, pitch and yaw from gyroscope
            gyro_roll=self.data_dict["gyro_roll"][-1]+dt*gyro_x
            self.data_dict["gyro_roll"].append(gyro_roll)
            
            gyro_pitch=self.data_dict["gyro_pitch"][-1]+dt*gyro_y
            self.data_dict["gyro_pitch"].append(gyro_pitch)

            K=1.
            gyro_yaw=K*(self.data_dict["gyro_yaw"][-1]/K+dt*gyro_z)
            self.data_dict["gyro_yaw"].append(gyro_yaw)
            print(gyro_yaw)

            # Fusion and filtering of data
            #
            forceMagnitude=abs(acc_x)+abs(acc_y)+abs(acc_z)
            print(forceMagnitude)

            if(forceMagnitude> 0 and forceMagnitude < 0):
                print("reached")

            last_roll=self.data_dict["roll"][-1]
            roll=self.alpha*(last_roll-gyro_x*dt)-(1-self.alpha)*acc_roll
            self.data_dict["roll"].append(roll)

            last_pitch=self.data_dict["pitch"][-1]
            pitch=self.alpha*(last_pitch+gyro_y*dt)-(1-self.alpha)*acc_pitch
            self.data_dict["pitch"].append(pitch)



            self.publish_ros()

    def calibrate(self):
        print("CALIBRATING===========================")
        self.acc_x_cal=sum(self.data_dict["AcX"][0:self.N_sample])/self.N_sample
        self.acc_y_cal=sum(self.data_dict["AcY"][0:self.N_sample])/self.N_sample
        self.acc_z_cal=0

        self.gyro_x_cal=sum(self.data_dict["GyX"][0:self.N_sample])/self.N_sample
        self.gyro_y_cal=sum(self.data_dict["GyY"][0:self.N_sample])/self.N_sample
        self.gyro_z_cal=sum(self.data_dict["GyZ"][0:self.N_sample])/self.N_sample

        self.calibrated=True

    def pop_data(self, data_list):
        data_list.append(random.randint(0,100))

if __name__ == '__main__':
    def debug():
        plt.figure()
        plt.title("acc_pitch")
        plt.plot(data.data_dict["acc_pitch"])

        plt.figure()
        plt.title("gyro_pitch")
        plt.plot(data.data_dict["gyro_pitch"])

        plt.figure()
        plt.title("pitch")
        plt.plot(data.data_dict["pitch"])
        
        plt.show()

    rospy.init_node('IMU_publisher', anonymous=True)
        
    x_max=300
    y_max=8000

    # Set up animation
    # please keep in mind that the label of a line is used for ploting data
    fig = plt.figure(0)
    ax1=plt.subplot(331)
    plt.title("Acc")
    r1=[[0, x_max], [-y_max, y_max]]
    accX, = ax1.plot([],[],label="AcX")
    accY, = ax1.plot([],[],label="AcY")
    accZ, = ax1.plot([],[],label="AcZ")
    
    ax2=plt.subplot(332)
    plt.title("Gy")
    r2=[[0, x_max], [-200, 200]]
    gyroX, = ax2.plot([],[], label="GyX")
    gyroY, = ax2.plot([],[], label="GyY")
    gyroZ, = ax2.plot([],[], label="GyZ")

    ax3=plt.subplot(333)
    plt.title("acc_roll")
    acc_roll, = ax3.plot([],[], label="acc_roll")

    ax4=plt.subplot(334)
    plt.title("acc_pitch")
    acc_pitch, = ax4.plot([],[], label="acc_pitch")

    ax5=plt.subplot(335)
    plt.title("gyro_roll")
    gyro_roll, = ax5.plot([],[], label="gyro_roll")

    ax6=plt.subplot(336)
    plt.title("gyro_pitch")
    gyro_pitch, = ax6.plot([],[], label="gyro_pitch")

    ax7=plt.subplot(337)
    plt.title("gyro_yaw")
    gyro_yaw, = ax7.plot([],[], label="gyro_yaw")

    ax8=plt.subplot(338)
    plt.title("roll")
    roll, = ax8.plot([],[], label="roll")

    ax9=plt.subplot(339)
    plt.title("pitch")
    pitch, = ax9.plot([],[], label="pitch")
    
    lines=[accX, accY, accZ, gyroX, gyroY, gyroZ, acc_pitch, acc_roll, gyro_roll, gyro_pitch, gyro_yaw, roll, pitch]

    #Create data container
    try:
        data=DataContainer(lines)
        data.daemon=True
        data.start()
    except(KeyboardInterrupt, SystemExit):
        print('\n! Received keyboard interrupt, quitting threads.\n')

    anim = animation.FuncAnimation(fig, data.update, interval=100)
    plt.show()

   



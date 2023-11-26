import time
import board
import busio
import math
import digitalio
import microcontroller
import neopixel
import os
from adafruit_bno08x import (
    BNO_REPORT_ACCELEROMETER,
    BNO_REPORT_GYROSCOPE,
    BNO_REPORT_MAGNETOMETER,
    BNO_REPORT_ROTATION_VECTOR,
    BNO_REPORT_GRAVITY,
)
from adafruit_bno08x.i2c import BNO08X_I2C

i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)
bno = BNO08X_I2C(i2c)

bno.enable_feature(BNO_REPORT_ROTATION_VECTOR)

new_file_name = f"data{str(len(os.listdir()))}.csv"

print("Writing output to:", new_file_name)
print("Waiting for start button")

button = digitalio.DigitalInOut(board.BUTTON)
button.direction = digitalio.Direction.INPUT
button.pull = digitalio.Pull.DOWN

pixel = neopixel.NeoPixel(board.NEOPIXEL, 1)
pixel.brightness = 0.1

pixel.fill((255, 0, 0))

started = False
while not started:
    if not button.value:
        started=True
    time.sleep(0.1)

pixel.fill((200, 80, 0))

print("Calibrating")
roll_adjust = None
pitch_adjust = None
yaw_adjust = None

quat_adjust = []

time.sleep(1)
for a in range(10):
    quat_i, quat_j, quat_k, quat_real = bno.quaternion
    quat_adjust = bno.quaternion
    roll_rad = math.atan2(2 * (quat_real * quat_i + quat_j * quat_k), 1 - 2 * (quat_i**2 + quat_j**2))
    pitch_rad = math.asin(2 * (quat_real * quat_j - quat_k * quat_i))
    yaw_rad = math.atan2(2 * (quat_real * quat_k + quat_i * quat_j), 1 - 2 * (quat_j**2 + quat_k**2))
    roll_adjust = math.degrees(roll_rad)
    pitch_adjust = math.degrees(pitch_rad)
    yaw_adjust = math.degrees(yaw_rad)
    time.sleep(0.1)

quat_adjust = [-quat_adjust[0], -quat_adjust[1], -quat_adjust[2], quat_adjust[3]]
print(quat_adjust)
time.sleep(5)
print("Calibration complete:")
print(f"{roll_adjust},{pitch_adjust},{yaw_adjust}\n")

pixel.fill((0, 255, 0))

def multiply_quaternions(q1, q2):
    # Unpack the quaternions
    b1, c1, d1, a1 = q1
    b2, c2, d2, a2 = q2

    # Compute the product
    real = a1*a2 - b1*b2 - c1*c2 - d1*d2
    i = a1*b2 + b1*a2 + c1*d2 - d1*c2
    j = a1*c2 - b1*d2 + c1*a2 + d1*b2
    k = a1*d2 + b1*c2 - c1*b2 + d1*a2

    return [i, j, k, real]

try:
    with open("/" + new_file_name, "a") as fp:
        fp.write(f"0,{roll_adjust},{pitch_adjust},{yaw_adjust}\n")
        while started:
            #quat_i, quat_j, quat_k, quat_real = bno.quaternion
            quat_current = bno.quaternion
            quat_i, quat_j, quat_k, quat_real = bno.quaternion #multiply_quaternions(quat_current, quat_adjust)
            roll_rad = math.atan2(2 * (quat_real * quat_i + quat_j * quat_k), 1 - 2 * (quat_i**2 + quat_j**2))
            pitch_rad = math.asin(2 * (quat_real * quat_j - quat_k * quat_i))
            yaw_rad = math.atan2(2 * (quat_real * quat_k + quat_i * quat_j), 1 - 2 * (quat_j**2 + quat_k**2))
            # Convert to degrees
            roll = math.degrees(roll_rad)
            pitch = math.degrees(pitch_rad)
            yaw = math.degrees(yaw_rad)
            fp.write(f"{time.monotonic_ns()},{roll},{pitch},{yaw}\n")
            print(f"{time.monotonic_ns()},{roll},{pitch},{yaw}")
            if not button.value:
                started=False
            time.sleep(0.01)
except:
    print("Read Only")
    while started:
            #quat_i, quat_j, quat_k, quat_real = bno.quaternion

            quat_current = bno.quaternion
            quat_i, quat_j, quat_k, quat_real = bno.quaternion #multiply_quaternions(quat_current, quat_adjust)

            roll_rad = math.atan2(2 * (quat_real * quat_i + quat_j * quat_k), 1 - 2 * (quat_i**2 + quat_j**2))
            pitch_rad = math.asin(2 * (quat_real * quat_j - quat_k * quat_i))
            yaw_rad = math.atan2(2 * (quat_real * quat_k + quat_i * quat_j), 1 - 2 * (quat_j**2 + quat_k**2))

            # Convert to degrees
            roll = math.degrees(roll_rad)
            pitch = math.degrees(pitch_rad)
            yaw = math.degrees(yaw_rad)
            print(f"{time.monotonic_ns()},{roll},{pitch},{yaw}")
            if not button.value:
                started=False
            time.sleep(0.01)

pixel.fill((255, 0, 0))
time.sleep(5)

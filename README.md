# Foot IMU Data Analysis

## Project Overview

This project is a foot-mounted sensor that collects data around a user's foot pitch and roll as the user walks.  Data is collected on an ESP32 microcontroller that is connected to a BNO08X 9-axis IMU, and is uploaded to a cloud database.  By comparing the gait patterns of a user's feet, differences between gait between the left and right foot can be identified.  The intention is to use this data to determine if changes in gait can be used to predict upcoming injuries or track recovery from previous injuries.

## Hardware Components

* **Microcontroller:** [AdaFruit ESP32 Feather V2](https://www.adafruit.com/product/5400)
* **9-Axis IMU:** [BNO08X Breakout Board](https://www.adafruit.com/product/4754)
* **IMU to Microcontroller Connection:** [Stemma QT to QT cable](https://www.adafruit.com/product/5385)
* **Battery:** [Lithium Ion Polymer Battery 3.7V](https://www.adafruit.com/product/1578)
* **USB-C to USB-C Cable** - For connecting to computer

**Note:** Other ESP32 CircuitPython boards, BNO08X breakout boards, I2C compatible connectors, and batteries will likely work, however only the above have been tested.

## System Design
![System Design Image](https://raw.githubusercontent.com/cody-talmadge/foot-imu-data-analysis/main/docs/System%20Design.png)
1. When the device is turned on and the user indicates they would like to start collecting data, the IMU continually collects foot orientation data (in quaternion form) and sends it to the microcontroller over the I2C bus until the user indicates they would like to stop collecting data.
2. Once the data collection is complete, a file containing the data is stored on the microcontroller and assuming the device has wifi connectivity the microcontroller gets the current date and time from AdaFruit’s datetime API.
3. After the microcontroller has the current date and time, it attempts to sync all stored data files with the cloud over a custom built API by sending POST requests to an AWS
API Gateway endpoint. Data is streamed 500 data points at a time to avoid any
memory limits on the CPU.
4. All POST requests to the AWS API Gateway endpoint are redirected to an AWS Lambda
data store function.
5. The lambda function converts the quaternion points to euler angles and then either
stores the data in a new record in a DynamoDB table (if it is the first 500 points for a file), or appends the data to an existing record in a DynamoDB table (if data for the file has already been stored). The Lambda function then sends a response back to the microcontroller indicating that data storage was successful.
6. The user navigates to a web dashboard (this is a HTML/Javascript/CSS dashboard that was set up on an S3 bucket).
7. When the web dashboard is opened, it sends a GET request for file data to the same AWS API Gateway endpoint.
8. All GET requests to the AWS API Gateway endpoint are redirected to an AWS Lambda data read function.
9. The lambda function reads the file data from DynamoDB, persons an analysis on the data, and then sends the data back to the web dashboard in the API response.
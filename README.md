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
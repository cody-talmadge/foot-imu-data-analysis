import csv
import numpy as np
import matplotlib.pyplot as plt
import time as tm
import math
import scipy
from scipy.interpolate import make_interp_spline
from scipy.signal import find_peaks

ankle_data_right_raw = []

with open('../example-data/right-foot.csv', newline='') as csvfile:
    reader = csv.reader(csvfile, delimiter=',', quotechar='"')
    for row in reader:
        ankle_data_right_raw.append([float(col) for col in row])

ankle_data_right = np.array(ankle_data_right_raw)

time_right = ankle_data_right[:,0] / 1000000000
pitch_right = ankle_data_right[:,1]
roll_right = ankle_data_right[:,2]

smoothed_pitch = scipy.ndimage.gaussian_filter1d(pitch_right, sigma=2)
peaks, _ = find_peaks(pitch_right, prominence=1)  # play with the prominence value
troughs, _ = find_peaks(-pitch_right, prominence=1)  # for troughs, invert the signal

points = [[int(time), "peak"] for time in peaks]
points += [[int(time), "trough"] for time in troughs]
points.sort(key=lambda x:x[0])

steps = []
step_times = []
step_values = []
total_step_times = []
foot_down_times = []
pitch_max = []
pitch_min = []
roll_max = []
roll_min = []
roll_values = []

for i in range(len(points) - 2):
    if points[i][1] == "trough":
        continue
    point_num, point_type = points[i]
    point_time = time_right[point_num]
    point_value = pitch_right[point_num]

    next_num, next_type = points[i + 1]
    next_time = time_right[next_num]
    next_value = pitch_right[next_num]

    two_num, two_type = points[i + 2]
    two_time = time_right[two_num]
    two_value = pitch_right[two_num]

    #Make sure we're in a peak, trough, peak pattern
    if point_type == "trough" or next_type == "peak" or two_type == "trough":
        continue

    #Our peaks weren't high enough or our troughs weren't low enough to be a step
    if point_value < 5 or next_value > -50 or two_value < 5:
        continue

    step_time = two_time - point_time
    #The time was too fast or short to be a step
    if step_time > 2 or step_time < 0.5:
        continue

    #Now we know it's a step!
    steps.append((point_num, two_num))
    total_step_times.append(step_time)
    foot_down_times.append(next_time - point_time)

    roll_max.append(np.max(roll_right[point_num:two_num]))
    roll_min.append(np.min(roll_right[point_num:two_num]))

    pitch_max.append(point_value)
    pitch_min.append(next_value)

    step_values.append(pitch_right[point_num:two_num+1])
    roll_values.append(roll_right[point_num:two_num+1])
    step_times.append(time_right[point_num:two_num+1])

print("Number of Steps:", len(total_step_times))
print("Step Time Average:", round(np.mean(total_step_times),2), "s Step Time Std Dev:", round(np.std(total_step_times),2), "s")
print("Foot Down Time Average:", round(np.mean(foot_down_times),2), "s Foot Down Std Dev:", round(np.std(foot_down_times),2), "s")
print("Percent Time Foot Down:", round(np.mean(foot_down_times) / np.mean(total_step_times) * 100, 1), "%")
print("Average Pitch Range:", round(np.mean(pitch_max), 1), "° to ", round(np.mean(pitch_min), 1), "°")
print("Average Roll Range:", round(np.mean(roll_max), 1), "° to ", round(np.mean(roll_min), 1), "°")


# plt.plot(time_right, pitch_right, label='Original Data', alpha=0.25)
# plt.plot(time_right, roll_right, label='Original Data', alpha=0.25)
# plt.plot(time_right, smoothed_pitch, label='Smoothed Data', alpha=0.6)
# plt.scatter(time_right[peaks], pitch_right[peaks], color='r', label='Peaks')
# plt.scatter(time_right[troughs], pitch_right[troughs], color='g', label='Troughs')

average_number_of_steps = 30
pitch_average = [[] for _ in range(average_number_of_steps)]
pitch_average_time = [i * np.mean(total_step_times) / (average_number_of_steps - 1) for i in range(average_number_of_steps)]
roll_average = [[] for _ in range(average_number_of_steps)]
for i in range(len(step_values)):
    start_step_time = step_times[i][0]
    end_step_time = step_times[i][-1]
    step_amount = (end_step_time - start_step_time) / (average_number_of_steps - 1)
    for j in range(len(step_values[i])):
        curr_time = step_times[i][j] - start_step_time
        list_element = int(curr_time / step_amount)
        pitch_average[list_element].append(step_values[i][j])
        roll_average[list_element].append(roll_values[i][j])
    plt.plot(step_times[i] - start_step_time, step_values[i], color="b", alpha=0.1, linewidth=1)
    plt.plot(step_times[i] - start_step_time, roll_values[i], color="r", alpha=0.1, linewidth=1)

for i in range(len(pitch_average)):
    pitch_average[i] = sum(pitch_average[i]) / len(pitch_average[i])
    roll_average[i] = sum(roll_average[i]) / len(roll_average[i])

Pitch_Spline = make_interp_spline(pitch_average_time, pitch_average)
Time_ = np.linspace(np.min(pitch_average_time), np.max(pitch_average_time), 500)
Pitch_ = Pitch_Spline(Time_)

Roll_Spline = make_interp_spline(pitch_average_time, roll_average)
Roll_ = Roll_Spline(Time_)


# plt.plot(pitch_average_time, pitch_average, color="b", alpha=1, linewidth=2, label="Average Step Pitch Angle")
# plt.plot(pitch_average_time, roll_average, color="r", alpha=1, linewidth=2, label="Average Step Roll Angle")
plt.plot(Time_, Roll_, color="r", alpha=1, linewidth=3, label="Average Step Roll Angle")
plt.plot(Time_, Pitch_, color="b", alpha=1, linewidth=3, label="Average Step Pitch Angle")
plt.legend()    
plt.show()



# plt.plot(time, np.append([0], pitch_rate))
# plt.plot(time, pitch)
# # plt.plot(time, np.append([0], np.diff(yaw)))
# # plt.plot(time, yaw)
# plt.plot(time, np.append([0], pitch_rate))
# plt.plot(time[0:-1], adjusted_yaw_rate)
# plt.plot(time[0:-1], yaw_rate)
# plt.plot(time_right, roll_right, label="Roll Right")
# plt.plot(time_right, pitch_right, label="Pitch Right")

# # plt.xlim(93, 98)
# # plt.plot(time, yaw, label="yaw")
# plt.legend()
# plt.show()

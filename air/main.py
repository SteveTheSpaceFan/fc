import math
from init import *
import csv
import utm
from multiprocessing import Process


def level0ControlLoop(readyToArm, start_FlightInit, readyToFly, current_X, current_Y, current_Heading, init_x, init_y, init_imu_heading, init_gps_altitude, touch_down_x,
                      touch_down_y, shared_pitch, shared_roll, shared_imu_heading, shared_raw_aileron_input,
                      shared_raw_elevator_input, shared_accceleration, desired_pitch, desired_roll, aileronTrim, elevatorTrim,
                      desired_vs, desired_heading, desired_throttle, manual_throttle_unlocked, calibrate_heading, imu_heading_compensation, flight_mode, manual_throttle_input,
                      manual_roll_change_per_sec, manual_pitch_change_per_sec, circle_altitude, circle_bankAngle,
                      Baro_altitude, Baro_vertical_speed, last_Baro_altitude, last_Baro_vertical_speed, Baro_temperature, last_Baro_temperature,
                      Pitot_pressure, Pitot_temperature, GPS_locked, GPS_latitude, GPS_longitude, GPS_altitude, GPS_speed, GPS_heading, GPS_satellites,
                      GPS_coord_x, GPS_coord_y, telemetry_mode, last_received_upLink, since_last_received_upLink, blackBox_path,
                      start_up_time, control_loop_interval, secondary_loop_interval, max_acceleration):
    # internal
    in_manual_control_mode = False
    # special cases
    exceed_Max_BankAngle = False
    over_loading = False
    stall = False
    # attitude
    pitch = 0
    roll = 0
    heading = 0
    last_pitch = 0
    last_roll = 0
    last_heading = 0
    attitude_new_data_weight = 1 - attitude_data_smooth_out
    # angular velocity
    pitch_speed = None
    roll_speed = None
    yaw_speed = None
    last_pitch_speed = 0
    last_roll_speed = 0
    last_yaw_speed = 0
    angular_velocity_new_data_weight = 1 - angular_velocity_data_smooth_out
    # acceleration
    IMU_acceleration = 9.81
    # linear acceleration
    IMU_acc_x = None
    IMU_acc_y = None
    IMU_acc_z = None
    last_IMU_acc_x = 0
    last_IMU_acc_y = 0
    last_IMU_acc_z = 0
    IMU_acc_new_data_weight = 1 - IMU_acc_data_smooth_out
    # controls
    desired_pitch_internal = 0
    desired_roll_internal = 0
    aileronTrim_internal = aileronTrim.value
    elevatorTrim_internal = elevatorTrim.value
    last_aileron_input = 0
    last_elevator_input = 0
    raw_aileron_input = None
    raw_elevator_input = None

    last_control_loop_update_time = time.monotonic()
    last_secondary_loop_update_time = time.monotonic()

    while True:
        time.sleep(0.0005)
        current_time = time.monotonic()
        control_loop_elapsed = current_time - last_control_loop_update_time
        secondary_loop_elapsed = current_time - last_secondary_loop_update_time

        # control_loop
        if control_loop_elapsed > control_loop_interval:
            last_control_loop_update_time = current_time
            # print(control_loop_elapsed)

            # IMU
            # attitude
            imu_attitute = imu.euler
            pitch_ = imu_attitute[1]
            if pitch_ is not None:
                if pitch_ <= 90 and pitch_ >= -90:
                    pitch = (
                        pitch_ * attitude_new_data_weight
                        + last_pitch * attitude_data_smooth_out
                    )
                    last_pitch = pitch

                roll_ = imu_attitute[2]
                if roll_ <= 180 and roll_ >= -180:
                    roll_ = -roll_
                    if roll_ * last_roll > 0:
                        roll = (
                            roll_ * attitude_new_data_weight
                            + last_roll * attitude_data_smooth_out
                        )
                    else:  # 180 -> -180
                        roll = roll_
                    last_roll = roll

                heading_ = imu_attitute[0]
                if heading_ <= 360 and heading_ >= 0:
                    heading = (
                        heading_ * attitude_new_data_weight
                        + last_heading * attitude_data_smooth_out
                    )
                    last_heading = heading

            # angular velocity
            imu_angular_velocity = imu.gyro  # [roll,pitch,yaw]
            roll_speed_ = imu_angular_velocity[0]
            if roll_speed_ is not None:
                roll_speed = (
                    roll_speed_ * angular_velocity_new_data_weight
                    + last_roll_speed * angular_velocity_data_smooth_out
                )
                last_roll_speed = roll_speed

                pitch_speed_ = imu_angular_velocity[1]
                pitch_speed = (
                    pitch_speed_ * angular_velocity_new_data_weight
                    + last_pitch_speed * angular_velocity_data_smooth_out
                )
                last_pitch_speed = pitch_speed

                yaw_speed_ = imu_angular_velocity[2]
                yaw_speed = (
                    yaw_speed_ * angular_velocity_new_data_weight
                    + last_yaw_speed * angular_velocity_data_smooth_out
                )
                last_yaw_speed = yaw_speed

            # acceleration
            imu_raw_acc = imu.acceleration
            if imu_raw_acc[0] is not None:
                _IMU_acceleration = math.sqrt(
                    imu_raw_acc[0]**2+imu_raw_acc[1]**2+imu_raw_acc[2]**2)
                if _IMU_acceleration > 0 and _IMU_acceleration < 200:
                    IMU_acceleration = _IMU_acceleration

            # linear_acceleration
            # imu_linear_acc = imu.linear_acceleration
            # IMU_acc_x_ = imu_linear_acc[0]
            # if IMU_acc_x_ is not None:
            #     IMU_acc_x = (
            #         IMU_acc_x_ * IMU_acc_new_data_weight
            #         + last_IMU_acc_x * IMU_acc_data_smooth_out
            #     )
            #     last_IMU_acc_x = IMU_acc_x

            #     IMU_acc_y_ = imu_linear_acc[1]
            #     IMU_acc_y = (
            #         IMU_acc_y_ * IMU_acc_new_data_weight
            #         + last_IMU_acc_y * IMU_acc_data_smooth_out
            #     )
            #     last_IMU_acc_y = IMU_acc_y

            #     IMU_acc_z_ = imu_linear_acc[2]
            #     IMU_acc_z = (
            #         IMU_acc_z_ * IMU_acc_new_data_weight
            #         + last_IMU_acc_z * IMU_acc_data_smooth_out
            #     )
            #     last_IMU_acc_z = IMU_acc_z

            # controls
            if not in_manual_control_mode:
                # check for special cases
                if roll < max_BankAngle / 2 and roll > -max_BankAngle / 2:
                    exceed_Max_BankAngle = False
                elif roll > max_BankAngle or roll < -max_BankAngle:
                    exceed_Max_BankAngle = True
                if IMU_acceleration > max_acceleration:
                    over_loading = True
                # translate to rawinputs
                raw_aileron_input = controlInputRequired(
                    roll,
                    roll_speed,
                    desired_roll_internal,
                    control_softness,
                    roll_authority,
                )
                raw_elevator_input = controlInputRequired(
                    pitch,
                    pitch_speed,
                    desired_pitch_internal,
                    control_softness,
                    pitch_authority,
                )
                # special cases
                if over_loading:
                    max_elevator_input_underLoad = last_elevator_input*0.5
                    if raw_elevator_input > max_elevator_input_underLoad:
                        raw_elevator_input = max_elevator_input_underLoad
                if exceed_Max_BankAngle:
                    raw_aileron_input *= 1.5
                    raw_elevator_input = 0
                # execute the controls
                if raw_aileron_input > 1:  # raw control capped out at 100%
                    raw_aileron_input = 1
                elif raw_aileron_input < -1:
                    raw_aileron_input = -1
                if raw_elevator_input > 1:
                    raw_elevator_input = 1
                elif raw_elevator_input < -1:
                    raw_elevator_input = -1
                last_aileron_input = raw_aileron_input
                last_elevator_input = raw_elevator_input
                aileron_actuation(raw_aileron_input, aileronTrim_internal)
                elevator_actuation(raw_elevator_input, elevatorTrim_internal)
                # restore the special cases
                over_loading = False

        # secondary loop
        if secondary_loop_elapsed > secondary_loop_interval:
            last_secondary_loop_update_time = current_time
            # print(secondary_loop_elapsed)
            if flight_mode.value == 0:
                in_manual_control_mode = True
            else:
                in_manual_control_mode = False

            # share the telemetry
            shared_pitch.value = pitch
            shared_roll.value = roll
            shared_imu_heading.value = heading
            shared_accceleration.value = IMU_acceleration
            if not in_manual_control_mode:
                shared_raw_aileron_input.value = raw_aileron_input
                shared_raw_elevator_input.value = raw_elevator_input
            # fetch the commands
            desired_pitch_internal = desired_pitch.value
            desired_roll_internal = desired_roll.value
            aileronTrim_internal = aileronTrim.value
            elevatorTrim_internal = elevatorTrim.value
            # print(raw_elevator_input)


def higherlevelControlLoop(readyToArm, start_FlightInit, readyToFly, current_X, current_Y, current_Heading, init_x, init_y, init_imu_heading, init_gps_altitude, touch_down_x,
                           touch_down_y, shared_pitch, shared_roll, shared_imu_heading, shared_raw_aileron_input,
                           shared_raw_elevator_input, shared_accceleration, desired_pitch, desired_roll, aileronTrim, elevatorTrim,
                           desired_vs, desired_heading, desired_throttle, manual_throttle_unlocked, calibrate_heading, imu_heading_compensation, flight_mode, manual_throttle_input,
                           manual_roll_change_per_sec, manual_pitch_change_per_sec, circle_altitude, circle_bankAngle,
                           Baro_altitude, Baro_vertical_speed, last_Baro_altitude, last_Baro_vertical_speed, Baro_temperature, last_Baro_temperature,
                           Pitot_pressure, Pitot_temperature, GPS_locked, GPS_latitude, GPS_longitude, GPS_altitude, GPS_speed, GPS_heading, GPS_satellites,
                           GPS_coord_x, GPS_coord_y, telemetry_mode, last_received_upLink, since_last_received_upLink, blackBox_path,
                           start_up_time, control_loop_interval, secondary_loop_interval, max_acceleration):

    Baro_altitude_new_data_weight = 1 - Baro_altitude_data_smooth_out
    Baro_vertical_speed_new_data_weight = 1 - Baro_vertical_speed_data_smooth_out
    Baro_temperature_new_data_weight = 1 - Baro_temperature_data_smooth_out

    higherlevelControl_loop_interval = 1 / secondary_loop_freq
    gps_loop_interval = 1 / gps_loop_freq
    last_higherlevelControl_loop_update_time = time.monotonic()
    last_gps_loop_update_time = time.monotonic()
    blackBox_startingTimeStamp = time.monotonic()
    # init flight (start_FlightInit)
    flightInitCompleted = False
    flightInit_in_progress = False
    init_x_accumulater = []
    init_y_accumulater = []
    init_imu_heading_accumulater = []
    init_gps_altitude_accumulater = []
    # autoTrim
    autoTrim_effectiveness = 1/(secondary_loop_freq*10)
    # calibrate_heading
    heading_calibrate_On = True
    heading_calibration_effectiveness = 1/(gps_loop_freq*10)

    with open(blackBox_path, "w") as blackBox:
        blackBoxWriter = csv.writer(blackBox, delimiter=",")
        blackBoxWriter.writerow(
            [
                "time",
                "pitch",
                "roll",
                "heading",
                "aileronInput",
                "elevatorInput",
                "Baro_altitude",
                "Baro_vertical_speed",
                "Baro_temperature",
                "GPS_locked",
                "GPS_coord_x",
                "GPS_coord_y",
                "GPS_altitude",
                "GPS_heading",
                "GPS_speed",
                "GPS_satellites",
                "aileronTrim",
                "elevatorTrim",
                "accceleration"
            ]
        )  # header
        while True:
            time.sleep(0.0005)
            current_time = time.monotonic()
            higherlevelControl_loop_elapsed = current_time - \
                last_higherlevelControl_loop_update_time
            gps_loop_elapsed = current_time - last_gps_loop_update_time

            # sensor update & #Flight control
            if higherlevelControl_loop_elapsed > higherlevelControl_loop_interval:
                last_higherlevelControl_loop_update_time = current_time
                # print(higherlevelControl_loop_elapsed)
                # Baro
                Baro_altitude_ = barometer.altitude
                if Baro_altitude_ is not None:
                    Baro_altitude.value = (
                        last_Baro_altitude * Baro_altitude_data_smooth_out
                        + Baro_altitude_ * Baro_altitude_new_data_weight
                    )
                    Baro_vertical_speed.value = (
                        (Baro_altitude.value - last_Baro_altitude)
                        * Baro_vertical_speed_new_data_weight
                        + last_Baro_vertical_speed
                        * higherlevelControl_loop_elapsed
                        * Baro_vertical_speed_data_smooth_out
                    ) / higherlevelControl_loop_elapsed
                    last_Baro_vertical_speed = Baro_vertical_speed.value
                    last_Baro_altitude = Baro_altitude.value
                Baro_temperature_ = barometer.temperature
                if Baro_temperature_ is not None:
                    Baro_temperature.value = (
                        last_Baro_temperature * Baro_altitude_data_smooth_out
                        + Baro_temperature_ * Baro_temperature_new_data_weight
                    )
                    last_Baro_temperature = Baro_temperature.value
                # Pitot
                Pitot_pressure_ = pitot.pressure
                if Pitot_pressure_ is not None:
                    Pitot_pressure.value = Pitot_pressure_
                Pitot_temperature_ = pitot.temperature
                if Pitot_temperature_ is not None:
                    Pitot_temperature.value = Pitot_temperature_
                #

                # Flight control
                # readyToArm
                if not flightInitCompleted:
                    time_since_start_up = time.time()-start_up_time
                    if time_since_start_up > 10 and GPS_locked.value == 1 and readyToArm.value == 0:
                        readyToArm.value = 1
                        print("readyToArm")

                if flightInitCompleted:
                    # throttle
                    if manual_throttle_unlocked.value:
                        throttle_control(manual_throttle_input.value)
                    else:
                        throttle_control(desired_throttle.value)
                    # level2ControlLoop
                    if flight_mode.value == 1:
                        desired_pitch.value += manual_pitch_change_per_sec.value * \
                            higherlevelControl_loop_interval
                        desired_roll.value += manual_roll_change_per_sec.value * \
                            higherlevelControl_loop_interval
                    else:
                        heading_diff = desired_heading.value - GPS_heading.value
                        vs_diff = desired_vs.value - Baro_vertical_speed.value

                    if desired_roll.value > normal_BankAngle:
                        desired_roll.value = normal_BankAngle
                    elif desired_roll.value < -normal_BankAngle:
                        desired_roll.value = -normal_BankAngle

                    if desired_pitch.value > normal_pitch:
                        desired_pitch.value = normal_pitch
                    elif desired_pitch.value < -normal_pitch:
                        desired_pitch.value = -normal_pitch
                    # level3ControlLoop
                    # autoTrim
                    if flight_mode.value != 0:
                        aileronTrim.value += (shared_raw_aileron_input.value -
                                              aileronTrim.value)*autoTrim_effectiveness
                        elevatorTrim.value += (shared_raw_elevator_input.value -
                                               elevatorTrim.value)*autoTrim_effectiveness

            if gps_loop_elapsed > gps_loop_interval:
                last_gps_loop_update_time = current_time
                # print(gps_loop_elapsed)
                gps.update()
                # Every second print out current location details if there's a fix.
                if not gps.has_3d_fix:
                    GPS_locked.value = 0
                else:
                    GPS_locked.value = 1
                    GPS_latitude.value = gps.latitude
                    GPS_longitude.value = gps.longitude
                    GPS_coord_x.value, GPS_coord_y.value, _, _ = utm.from_latlon(
                        GPS_latitude.value, GPS_longitude.value
                    )
                    if ksp_mode:
                        GPS_coord_x.value, GPS_coord_y.value = GPS_coord_x.value * \
                            600/6371, GPS_coord_y.value*600/6371

                    # print("Fix quality: {}".format(gps.fix_quality))
                    # Some attributes beyond latitude, longitude and timestamp are optional
                    # and might not be present.  Check if they're None before trying to use!
                    if gps.satellites is not None:
                        GPS_satellites.value = gps.satellites
                    if gps.altitude_m is not None:
                        GPS_altitude.value = gps.altitude_m
                    if gps.speed_knots is not None:
                        GPS_speed.value = gps.speed_knots * 0.51444
                    if gps.track_angle_deg is not None:
                        GPS_heading.value = gps.track_angle_deg

                    # calibrate_heading
                    if heading_calibrate_On:
                        imu_heading_compensation.value += ((GPS_heading.value - shared_imu_heading.value) -
                                                           imu_heading_compensation.value)*heading_calibration_effectiveness
                    # init Flight
                    if not flightInitCompleted:
                        if start_FlightInit.value and not flightInit_in_progress:
                            flightInit_in_progress = True
                            print("flightInit_in_progress")
                        elif flightInit_in_progress:
                            init_x_accumulater.append(GPS_coord_x.value)
                            init_y_accumulater.append(GPS_coord_y.value)
                            init_imu_heading_accumulater.append(
                                shared_imu_heading.value)
                            init_gps_altitude_accumulater.append(
                                GPS_altitude.value)
                            if len(init_x_accumulater) >= 10:
                                init_x.value = resonable_mean(
                                    init_x_accumulater)
                                init_x_accumulater = []
                                init_y.value = resonable_mean(
                                    init_y_accumulater)
                                init_y_accumulater = []
                                init_imu_heading.value = resonable_mean(
                                    init_imu_heading_accumulater)
                                init_imu_heading_accumulater = []
                                init_gps_altitude.value = resonable_mean(
                                    init_gps_altitude_accumulater)
                                init_gps_altitude_accumulater = []
                                flightInitCompleted = True
                                blackBox_startingTimeStamp = time.monotonic()
                                readyToFly.value = 1
                                print("flightInitCompleted")

                # data recorder (blackBox)
                if flightInitCompleted:  # start_FlightInit
                    timeStamp = round(
                        current_time - blackBox_startingTimeStamp, 3)
                    record = [
                        timeStamp,
                        round(shared_pitch.value, 2),
                        round(shared_roll.value, 2),
                        round(shared_imu_heading.value, 2),
                        round(shared_raw_aileron_input.value, 2),
                        round(shared_raw_elevator_input.value, 2),
                        round(Baro_altitude.value, 2),
                        round(Baro_vertical_speed.value, 2),
                        round(Baro_temperature.value, 2),
                        int(GPS_locked.value),
                        round(GPS_coord_x.value, 2),
                        round(GPS_coord_y.value, 2),
                        round(GPS_altitude.value, 2),
                        round(GPS_heading.value, 2),
                        round(GPS_speed.value, 2),
                        int(GPS_satellites.value),
                        round(aileronTrim.value, 2),
                        round(elevatorTrim.value, 2),
                        round(shared_accceleration.value, 2),
                    ]
                    blackBoxWriter.writerow(record)
                    # print("wrote at "+str(timeStamp))


def commLoop(readyToArm, start_FlightInit, readyToFly, current_X, current_Y, current_Heading, init_x, init_y, init_imu_heading, init_gps_altitude, touch_down_x,
             touch_down_y, shared_pitch, shared_roll, shared_imu_heading, shared_raw_aileron_input,
             shared_raw_elevator_input, shared_accceleration, desired_pitch, desired_roll, aileronTrim, elevatorTrim,
             desired_vs, desired_heading, desired_throttle, manual_throttle_unlocked, calibrate_heading, imu_heading_compensation, flight_mode, manual_throttle_input,
             manual_roll_change_per_sec, manual_pitch_change_per_sec, circle_altitude, circle_bankAngle,
             Baro_altitude, Baro_vertical_speed, last_Baro_altitude, last_Baro_vertical_speed, Baro_temperature, last_Baro_temperature,
             Pitot_pressure, Pitot_temperature, GPS_locked, GPS_latitude, GPS_longitude, GPS_altitude, GPS_speed, GPS_heading, GPS_satellites,
             GPS_coord_x, GPS_coord_y, telemetry_mode, last_received_upLink, since_last_received_upLink, blackBox_path,
             start_up_time, control_loop_interval, secondary_loop_interval, max_acceleration):

    telemetry_delim = ','

    while True:
        time.sleep(0.0005)
        receivedPacket = None
        receivedContent = None
        contentToSent = ""
        packetToSent = None

        # try:
        receivedPacket = rfm9x.receive(timeout=0.2)  # default timeout=.5
        if receivedPacket is not None and len(receivedPacket) > 0:
            receivedContent = receivedPacket.decode("ascii")
            tele_command = receivedContent[0]
            tele_payload = receivedContent[1:]
            # last update time
            received_time = time.time()
            since_last_received_upLink.value = received_time - last_received_upLink
            last_received_upLink = received_time

            if tele_command == '0':  # full manual
                if flight_mode.value != 0:
                    manual_throttle_unlocked.value = 1
                    print("full manual mode")
                    flight_mode.value = 0
                manual_aileron_input = (
                    (int(tele_payload[0:2])/99*100-50)*0.02)**3
                manual_elevator_input = (
                    (int(tele_payload[2:4])/99*100-50)*0.02)**3
                manual_throttle_input.value = (
                    int(tele_payload[4:6])/99*100-50)*0.02
                shared_raw_aileron_input.value = manual_aileron_input
                shared_raw_elevator_input.value = manual_elevator_input
                aileron_actuation(manual_aileron_input, aileronTrim.value)
                elevator_actuation(
                    manual_elevator_input, elevatorTrim.value)
            elif tele_command == '1':  # fly by wire (partial manual)
                if flight_mode.value != 1:
                    manual_throttle_unlocked.value = 1
                    flight_mode.value = 1

                desired_pitch.value = 5
                desired_roll.value = 0
                manual_roll_input = (
                    (int(tele_payload[0:2])/99*100-50)*0.02)**3
                manual_pitch_input = (
                    (int(tele_payload[2:4])/99*100-50)*0.02)**3
                manual_throttle_input.value = (
                    int(tele_payload[4:6])/99*100-50)*0.02

                desired_pitch.value = manual_pitch_input * max_pitch + 3
                desired_roll.value = manual_roll_input * max_BankAngle
            elif tele_command == '2':  # fully auto modes
                manual_throttle_unlocked.value = 0
                fully_auto_mode = int(tele_payload[0])
                flight_mode.value = int(tele_command + str(fully_auto_mode))
                manual_throttle_unlocked.value = 0
                if fully_auto_mode == 1:
                    circle_altitude.value = GPS_altitude.value
                    desired_pitch.value = toga_pitch/2
                    desired_roll.value = 25
                    desired_throttle.value = 0.75
                elif fully_auto_mode == 2:
                    desired_pitch.value = toga_pitch
                    desired_roll.value = 0
                    desired_throttle.value = toga_thrust
                    print("toga")
                elif fully_auto_mode == 3:
                    pass
                elif fully_auto_mode == 4:
                    pass
            elif tele_command == '9':  # Change Settings
                param_index = int(tele_payload[0:2])
                print(param_index)
                # init the flight
                if param_index == 0 and bool(readyToArm.value):
                    if readyToFly.value != 1:
                        start_FlightInit.value = 1
                elif param_index == 10 or param_index == 11:  # aileronTrim
                    if param_index == 11:
                        aileronTrim.value += trim_tick
                        if aileronTrim.value > 1:
                            aileronTrim.value = 1
                    else:
                        aileronTrim.value -= trim_tick
                        if aileronTrim.value < -1:
                            aileronTrim.value = -1
                elif param_index == 20 or param_index == 21:  # elevatorTrim
                    if param_index == 21:
                        elevatorTrim.value += trim_tick
                        if elevatorTrim.value > 1:
                            elevatorTrim.value = 1
                    else:
                        elevatorTrim.value -= trim_tick
                        if elevatorTrim.value < -1:
                            elevatorTrim.value = -1

        #     else:
        #         continue
        # except:
        #     continue

        # if telemetry_mode != 0:
        #     try:

        # plane_status
        plane_status = '0'
        if readyToFly.value:  # readyToFly
            pass
        elif start_FlightInit.value:  # FlightInit in progress
            plane_status = '1'
        elif readyToArm.value:  # readyToArm
            plane_status = '2'
        else:  # not readyToArm
            plane_status = '3'

        plane_mode = flight_mode.value

        plane_pitch = int(shared_pitch.value)
        plane_roll = int(shared_roll.value)
        plane_heading = int(shared_imu_heading.value)
        telemetry_data = [plane_status, plane_mode,
                          plane_pitch, plane_roll, plane_heading]

        contentToSent = telemetry_delim.join([str(x) for x in telemetry_data])
        packetToSent = contentToSent.encode("ascii")
        rfm9x.send(packetToSent)
        #     except:
        #         continue


thread1 = Process(target=level0ControlLoop, args=(readyToArm, start_FlightInit, readyToFly, current_X, current_Y, current_Heading, init_x, init_y, init_imu_heading, init_gps_altitude, touch_down_x,
                                                  touch_down_y, shared_pitch, shared_roll, shared_imu_heading, shared_raw_aileron_input,
                                                  shared_raw_elevator_input, shared_accceleration, desired_pitch, desired_roll, aileronTrim, elevatorTrim,
                                                  desired_vs, desired_heading, desired_throttle, manual_throttle_unlocked, calibrate_heading, imu_heading_compensation, flight_mode, manual_throttle_input,
                                                  manual_roll_change_per_sec, manual_pitch_change_per_sec, circle_altitude, circle_bankAngle,
                                                  Baro_altitude, Baro_vertical_speed, last_Baro_altitude, last_Baro_vertical_speed, Baro_temperature, last_Baro_temperature,
                                                  Pitot_pressure, Pitot_temperature, GPS_locked, GPS_latitude, GPS_longitude, GPS_altitude, GPS_speed, GPS_heading, GPS_satellites,
                                                  GPS_coord_x, GPS_coord_y, telemetry_mode, last_received_upLink, since_last_received_upLink, blackBox_path,
                                                  start_up_time, control_loop_interval, secondary_loop_interval, max_acceleration))
thread2 = Process(target=higherlevelControlLoop, args=(readyToArm, start_FlightInit, readyToFly, current_X, current_Y, current_Heading, init_x, init_y, init_imu_heading, init_gps_altitude, touch_down_x,
                                                       touch_down_y, shared_pitch, shared_roll, shared_imu_heading, shared_raw_aileron_input,
                                                       shared_raw_elevator_input, shared_accceleration, desired_pitch, desired_roll, aileronTrim, elevatorTrim,
                                                       desired_vs, desired_heading, desired_throttle, manual_throttle_unlocked, calibrate_heading, imu_heading_compensation, flight_mode, manual_throttle_input,
                                                       manual_roll_change_per_sec, manual_pitch_change_per_sec, circle_altitude, circle_bankAngle,
                                                       Baro_altitude, Baro_vertical_speed, last_Baro_altitude, last_Baro_vertical_speed, Baro_temperature, last_Baro_temperature,
                                                       Pitot_pressure, Pitot_temperature, GPS_locked, GPS_latitude, GPS_longitude, GPS_altitude, GPS_speed, GPS_heading, GPS_satellites,
                                                       GPS_coord_x, GPS_coord_y, telemetry_mode, last_received_upLink, since_last_received_upLink, blackBox_path,
                                                       start_up_time, control_loop_interval, secondary_loop_interval, max_acceleration))
thread3 = Process(target=commLoop, args=(readyToArm, start_FlightInit, readyToFly, current_X, current_Y, current_Heading, init_x, init_y, init_imu_heading, init_gps_altitude, touch_down_x,
                                         touch_down_y, shared_pitch, shared_roll, shared_imu_heading, shared_raw_aileron_input,
                                         shared_raw_elevator_input, shared_accceleration, desired_pitch, desired_roll, aileronTrim, elevatorTrim,
                                         desired_vs, desired_heading, desired_throttle, manual_throttle_unlocked, calibrate_heading, imu_heading_compensation, flight_mode, manual_throttle_input,
                                         manual_roll_change_per_sec, manual_pitch_change_per_sec, circle_altitude, circle_bankAngle,
                                         Baro_altitude, Baro_vertical_speed, last_Baro_altitude, last_Baro_vertical_speed, Baro_temperature, last_Baro_temperature,
                                         Pitot_pressure, Pitot_temperature, GPS_locked, GPS_latitude, GPS_longitude, GPS_altitude, GPS_speed, GPS_heading, GPS_satellites,
                                         GPS_coord_x, GPS_coord_y, telemetry_mode, last_received_upLink, since_last_received_upLink, blackBox_path,
                                         start_up_time, control_loop_interval, secondary_loop_interval, max_acceleration))

if __name__ == '__main__':
    thread1.start()
    thread2.start()
    thread3.start()
    thread1.join()
    thread2.join()
    thread3.join()

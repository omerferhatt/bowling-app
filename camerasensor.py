import numpy as np
import cv2
import time
import mysql.connector
import pickle


def take_image():
    global lane_image
    global lane_image_gray
    if cap.isOpened():
        ret, lane_image = cap.read()
        if ret:
            lane_image_gray = cv2.cvtColor(lane_image, cv2.COLOR_BGR2GRAY)
            cv2.imwrite('bowling-img-save/lane_image.jpg', lane_image)
            cv2.imwrite('bowling-img-save/lane_image_gray.jpg', lane_image_gray)
        else:
            print("Error opening video stream or file")


def set_pin_bounds():
    global pinBoundingBoxes
    pinBoundingBoxes = cv2.selectROIs("Select pins in order", lane_image, showCrosshair=True)
    cv2.destroyWindow("Select pins in order")


def set_line_bounds():
    global lineBoundBox
    lineBoundBox = cv2.selectROI('Select Line', lane_image, showCrosshair=True)
    cv2.destroyWindow('Select Line')


def ball_detection():
    global isBallPassed
    if cap.isOpened():
        ret, lane = cap.read()
        if ret:
            roi = lane[lineBoundBox[1]:lineBoundBox[1] + lineBoundBox[3],
                  lineBoundBox[0]:lineBoundBox[0] + lineBoundBox[2]]
            roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            lane2 = cv2.cvtColor(lane, cv2.COLOR_BGR2GRAY)
            diff = cv2.absdiff(roi, lane_image_gray[lineBoundBox[1]:lineBoundBox[1] + lineBoundBox[3],
                                    lineBoundBox[0]:lineBoundBox[0] + lineBoundBox[2]])

            thresh = cv2.threshold(diff, 50, 255, cv2.THRESH_BINARY)[1]
            thresh2 = cv2.threshold(lane2, 50, 255, cv2.THRESH_BINARY)[1]
            result = np.mean(thresh)

            if result > 40:
                cv2.putText(lane, "Ball Passed", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                isBallPassed = True

            else:
                cv2.putText(lane, "Ball not Passed", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                isBallPassed = False
            cv2.imshow('diff', thresh2)
            if cv2.waitKey(23) & 0xFF == ord('q'):
                pass
        return lane
    else:
        print("Error opening video stream or file")


def pin_detection():
    global pins
    pins = np.ndarray(shape=(10, 1))
    ret, lane = cap.read()
    if ret:
        index = 0
        for x, y, dx, dy in pinBoundingBoxes:

            roi = lane[y:y + dy, x:x + dx]
            _, thresh = cv2.threshold(roi, 90, 255, cv2.THRESH_BINARY)

            mean = np.mean(thresh)

            if mean > 200:
                cv2.rectangle(lane, (x, y), (x + dx, y + dy), (0, 255, 0), 3)
                pins[index] = 1

            else:
                cv2.rectangle(lane, (x, y), (x + dx, y + dy), (0, 0, 255), 3)
                pins[index] = 0

            index += 1

            cv2.putText(lane, "Ball Passed", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            cv2.putText(lane, f"{10 - int(np.sum(pins))} pin-s down", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (0, 0, 255), 2)
        if cv2.waitKey(23) & 0xFF == ord('q'):
            pass
        return lane
    else:
        print("Error opening video stream or file")


connection = mysql.connector.connect(
    host='localhost',
    user='root',
    passwd='871811')
cursor = connection.cursor(prepared=True)

device_name = 'raspberry2'
sql = f"SELECT lane FROM configuration.ip WHERE device_name = '{device_name}'"
cursor.execute(sql)
lane_number = int(cursor.fetchone()[0])

cap = cv2.VideoCapture('bowling-sample/lane-close-up-long.mp4')
take_image()

sql = f"SELECT pin10xydxdy FROM configuration.pin_location WHERE lane = '{lane_number}'"
cursor.execute(sql)
result = cursor.fetchone()[0]

if result is None:
    set_pin_bounds()
    pin = 1
    for x, y, dx, dy in pinBoundingBoxes:
        sql = f"UPDATE configuration.pin_location SET pin{pin}xydxdy = '{x},{y},{dx},{dy}' WHERE lane = '{lane_number}'"
        cursor.execute(sql)
        connection.commit()
        pin += 1
    with open('pinBoundingBoxes', 'wb') as f:
        pickle.dump(pinBoundingBoxes, f, protocol=pickle.HIGHEST_PROTOCOL)
else:
    with open('pinBoundingBoxes', 'rb') as f:
        pinBoundingBoxes = pickle.load(f)


sql = f"SELECT line_box FROM configuration.ball_line_location WHERE lane = '{lane_number}'"
cursor.execute(sql)
result = cursor.fetchone()[0]

if result is None:
    set_line_bounds()
    sql = f"""UPDATE configuration.ball_line_location SET line_box = 
        '{lineBoundBox[0]},{lineBoundBox[1]},{lineBoundBox[2]},{lineBoundBox[3]}' 
         WHERE lane = '{lane_number}'"""

    cursor.execute(sql)
    connection.commit()
    with open('lineBoundBox', 'wb') as f:
        pickle.dump(lineBoundBox, f, protocol=pickle.HIGHEST_PROTOCOL)
else:
    with open('lineBoundBox', 'rb') as f:
        lineBoundBox = pickle.load(f)

sql = f"SELECT idplayer FROM bowling.player WHERE game_idgame = '{lane_number}'"
cursor.execute(sql)
player_id = cursor.fetchall()

for frame in range(1, 10):
    for id_num in player_id[:][0]:
        shot = [None, None]
        for index in range(len(shot)):
            isBallPassed = False
            while not isBallPassed:
                take_image()
                timeout = time.time() + 2
                while time.time() < timeout:
                    lane = ball_detection()
                    if isBallPassed:
                        break
                    cv2.imshow('image', lane_image_gray)
                    cv2.imshow('Lane', lane)

            timeout = int(round(time.time() * 1000)) + 350
            while isBallPassed and int(round(time.time() * 1000)) < timeout:
                lane = pin_detection()
                cv2.imshow('Lane', lane)

            if frame > 0 and frame < 10:
                if index == 0:
                    shot[index] = 10 - int(np.sum(pins))
                    sql = f"UPDATE bowling.frame SET shot1 = '{shot[index]}' WHERE player_idplayer = '{id_num}' AND frame_number = '{frame}'"
                    cursor.execute(sql)
                    connection.commit()
                elif index == 1 and shot[0] != 10:
                    shot[index] = 10 - int(np.sum(pins)) - shot[0]
                    sql = f"UPDATE bowling.frame SET shot2 = '{shot[index]}' WHERE player_idplayer = '{id_num}' AND frame_number = '{frame}'"
                    cursor.execute(sql)
                    connection.commit()

            timeout = time.time() + 14
            while time.time() < timeout:
                cap.read()
                cv2.waitKey(23)

for id_num in player_id[:][0]:
    shot = [None, None, None]
    for index in range(len(shot)):
        isBallPassed = False
        while not isBallPassed:
            take_image()
            timeout = time.time() + 2
            while time.time() < timeout:
                lane = ball_detection()
                if isBallPassed:
                    break
                cv2.imshow('image', lane_image_gray)
                cv2.imshow('Lane', lane)

        timeout = int(round(time.time() * 1000)) + 650
        while isBallPassed and int(round(time.time() * 1000)) < timeout:
            lane = pin_detection()
            cv2.imshow('Lane', lane)

            if index == 0:
                shot[index] = 10 - int(np.sum(pins))
                sql = f"UPDATE bowling.frame SET shot1 = '{shot[index]}' WHERE player_idplayer = '{id_num}' AND frame_number = '{frame}'"
                cursor.execute(sql)
                connection.commit()
            elif index == 1:
                if shot[0] == 10:
                    shot[index] = 10 - int(np.sum(pins))
                    sql = f"UPDATE bowling.frame SET shot2 = '{shot[index]}' WHERE player_idplayer = '{id_num}' AND frame_number = '{frame}'"
                    cursor.execute(sql)
                    connection.commit()
                elif shot[0] != 10:
                    shot[index] = 10 - int(np.sum(pins)) - shot[0]
                    sql = f"UPDATE bowling.frame SET shot2 = '{shot[index]}' WHERE player_idplayer = '{id_num}' AND frame_number = '{frame}'"
                    cursor.execute(sql)
                    connection.commit()
            elif index == 2:
                if (shot[0] == 10 and shot[1] == 10) or (shot[0] + shot[1] == 10):
                    shot[index] = 10 - int(np.sum(pins))
                    sql = f"UPDATE bowling.frame SET shot3 = '{shot[index]}' WHERE player_idplayer = '{id_num}' AND frame_number = '{frame}'"
                    cursor.execute(sql)
                    connection.commit()
                elif shot[0] == 10:
                    shot[index] = 10 - int(np.sum(pins)) - shot[1]
                    sql = f"UPDATE bowling.frame SET shot3 = '{shot[index]}' WHERE player_idplayer = '{id_num}' AND frame_number = '{frame}'"
                    cursor.execute(sql)
                    connection.commit()

        timeout = time.time() + 14
        while time.time() < timeout:
            cap.read()
            cv2.waitKey(23)

cv2.destroyAllWindows()

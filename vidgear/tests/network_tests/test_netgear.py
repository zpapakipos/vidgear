"""
===============================================
vidgear library source-code is deployed under the Apache 2.0 License:

Copyright (c) 2019-2020 Abhishek Thakur(@abhiTronix) <abhi.una12@gmail.com>

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
===============================================
"""
# import the necessary packages

import os
import queue
import cv2
import numpy as np
import pytest
import random
import logging as log
import tempfile
from zmq.error import ZMQError

from vidgear.gears import NetGear, VideoGear
from vidgear.gears.helper import logger_handler

# define test logger
logger = log.getLogger("Test_netgear")
logger.propagate = False
logger.addHandler(logger_handler())
logger.setLevel(log.DEBUG)


def return_testvideo_path():
    """
    returns Test Video path
    """
    path = "{}/Downloads/Test_videos/BigBuckBunny_4sec.mp4".format(
        tempfile.gettempdir()
    )
    return os.path.abspath(path)


@pytest.mark.parametrize("address, port", [("www.idk.com", "5555"), (None, "5555")])
def test_playback(address, port):
    """
    Tests NetGear Bare-minimum network playback capabilities
    """
    stream = None
    server = None
    client = None
    try:
        # open stream
        stream = cv2.VideoCapture(return_testvideo_path())
        # open server and client with default params
        client = NetGear(address=address, port=port, receive_mode=True)
        server = NetGear(address=address, port=port)
        # playback
        while True:
            (grabbed, frame_server) = stream.read()
            if not grabbed:
                break
            server.send(frame_server)  # send
            frame_client = client.recv()  # recv
    except Exception as e:
        if (
            isinstance(e, (ZMQError, ValueError, RuntimeError))
            or address == "www.idk.com"
        ):
            logger.exception(str(e))
        else:
            pytest.fail(str(e))
    finally:
        # clean resources
        if not (stream is None):
            stream.release()
        if not (server is None):
            server.close()
        if not (client is None):
            client.close()


@pytest.mark.parametrize("receive_mode", [True, False])
def test_primary_mode(receive_mode):
    """
    Tests NetGear Bare-minimum network playback capabilities
    """
    stream = None
    conn = None
    try:
        # open stream
        options_gear = {"THREAD_TIMEOUT": 300}
        stream = VideoGear(source=return_testvideo_path(), **options_gear).start()
        frame = stream.read()
        # open server and client with default params
        conn = NetGear(receive_mode=receive_mode)
        if receive_mode:
            conn.send(frame)
        else:
            frame_client = conn.recv()
    except Exception as e:
        if isinstance(e, ValueError):
            pytest.xfail("Test Passed!")
        elif isinstance(e, queue.Empty):
            logger.exception(str(e))
        else:
            pytest.fail(str(e))
    finally:
        # clean resources
        if not (stream is None):
            stream.stop()
        if not (conn is None):
            conn.close()


@pytest.mark.parametrize(
    "pattern", [2, 3]
)  # 2:(zmq.PUB,zmq.SUB) (#3 is incorrect value)
def test_patterns(pattern):
    """
    Testing NetGear different messaging patterns
    """
    # define parameters
    options = {"flag": 0, "copy": False, "track": False}
    # initialize
    frame_server = None
    stream = None
    server = None
    client = None
    try:
        # open stream
        stream = cv2.VideoCapture(return_testvideo_path())
        client = NetGear(pattern=pattern, receive_mode=True, logging=True, **options)
        server = NetGear(pattern=pattern, logging=True, **options)
        # select random input frame from stream
        i = 0
        random_cutoff = random.randint(10, 100)
        while i < random_cutoff:
            (grabbed, frame_server) = stream.read()
            i += 1
        # check if input frame is valid
        assert not (frame_server is None)
        # send frame over network
        server.send(frame_server)
        frame_client = client.recv()
        # check if received frame exactly matches input frame
        assert np.array_equal(frame_server, frame_client)
    except Exception as e:
        if isinstance(e, (ZMQError, ValueError, RuntimeError)):
            logger.exception(str(e))
        else:
            pytest.fail(str(e))
    finally:
        # clean resources
        if not (stream is None):
            stream.release()
        if not (server is None):
            server.close()
        if not (client is None):
            client.close()


@pytest.mark.parametrize(
    "options_client",
    [
        {"compression_format": None, "compression_param": cv2.IMREAD_UNCHANGED},
        {
            "compression_format": ".jpg",
            "compression_param": [cv2.IMWRITE_JPEG_QUALITY, 80],
        },
    ],
)
def test_compression(options_client):
    """
    Testing NetGear's real-time frame compression capabilities
    """
    options = {
        "compression_format": ".jpg",
        "compression_param": [
            cv2.IMWRITE_JPEG_QUALITY,
            20,
            cv2.IMWRITE_JPEG_OPTIMIZE,
            True,
        ],
    }  # JPEG compression
    # initialize
    stream = None
    server = None
    client = None
    try:
        # open streams
        options_gear = {"THREAD_TIMEOUT": 300}
        stream = VideoGear(source=return_testvideo_path(), **options_gear).start()
        client = NetGear(pattern=0, receive_mode=True, logging=True, **options_client)
        server = NetGear(pattern=0, logging=True, **options)
        # send over network
        while True:
            frame_server = stream.read()
            if frame_server is None:
                break
            server.send(frame_server)
            frame_client = client.recv()
    except Exception as e:
        if isinstance(e, (ZMQError, ValueError, RuntimeError, queue.Empty)):
            logger.exception(str(e))
        else:
            pytest.fail(str(e))
    finally:
        # clean resources
        if not (stream is None):
            stream.stop()
        if not (server is None):
            server.close()
        if not (client is None):
            client.close()


test_data_class = [
    (0, 1, tempfile.gettempdir(), True),
    (0, 1, ["invalid"], True),
    (1, 1, "INVALID_DIRECTORY", False),
]


@pytest.mark.parametrize(
    "pattern, security_mech, custom_cert_location, overwrite_cert", test_data_class
)
def test_secure_mode(pattern, security_mech, custom_cert_location, overwrite_cert):
    """
    Testing NetGear's Secure Mode
    """
    # define security mechanism
    options = {
        "secure_mode": security_mech,
        "custom_cert_location": custom_cert_location,
        "overwrite_cert": overwrite_cert,
    }
    # initialize
    frame_server = None
    stream = None
    server = None
    client = None
    try:
        # open stream
        stream = cv2.VideoCapture(return_testvideo_path())
        # define params
        server = NetGear(pattern=pattern, logging=True, **options)
        client = NetGear(pattern=pattern, receive_mode=True, logging=True, **options)
        # select random input frame from stream
        i = 0
        while i < random.randint(10, 100):
            (grabbed, frame_server) = stream.read()
            i += 1
        # check input frame is valid
        assert not (frame_server is None)
        # send and recv input frame
        server.send(frame_server)
        frame_client = client.recv()
        # check if received frame exactly matches input frame
        assert np.array_equal(frame_server, frame_client)
    except Exception as e:
        if isinstance(e, (ZMQError, ValueError, RuntimeError)):
            logger.exception(str(e))
        elif (
            isinstance(e, AssertionError)
            and custom_cert_location == "INVALID_DIRECTORY"
        ):
            logger.exception(str(e))
        else:
            pytest.fail(str(e))
    finally:
        # clean resources
        if not (stream is None):
            stream.release()
        if not (server is None):
            server.close()
        if not (client is None):
            client.close()


@pytest.mark.parametrize(
    "pattern, target_data, options",
    [
        (0, [1, "string", ["list"]], {"bidirectional_mode": True}),
        (
            1,
            (np.random.random(size=(480, 640, 3)) * 255).astype(np.uint8),
            {
                "bidirectional_mode": True,
                "compression_format": ".jpg",
                "compression_param": (
                    cv2.IMREAD_COLOR,
                    [
                        cv2.IMWRITE_JPEG_QUALITY,
                        85,
                        cv2.IMWRITE_JPEG_PROGRESSIVE,
                        False,
                        cv2.IMWRITE_JPEG_OPTIMIZE,
                        True,
                    ],
                ),
            },
        ),
        (2, {1: "apple", 2: "cat"}, {"bidirectional_mode": True}),
    ],
)
def test_bidirectional_mode(pattern, target_data, options):
    """
    Testing NetGear's Bidirectional Mode with different data-types
    """
    # initialize
    stream = None
    server = None
    client = None
    try:
        logger.debug("Given Input Data: {}".format(target_data))
        # open stream
        options_gear = {"THREAD_TIMEOUT": 300}
        stream = VideoGear(source=return_testvideo_path(), **options_gear).start()
        # define params
        client = NetGear(pattern=pattern, receive_mode=True, **options)
        server = NetGear(pattern=pattern, **options)
        # get frame from stream
        frame_server = stream.read()
        assert not (frame_server is None)
        # check if target data is numpy ndarray
        if isinstance(target_data, np.ndarray):
            # sent frame and data from server to client
            server.send(target_data, message=target_data)
            # client receives the data and frame and send its data
            server_data, frame_client = client.recv(return_data=target_data)
            # server receives the data and cycle continues
            client_data = server.send(target_data, message=target_data)
            # logger.debug data received at client-end and server-end
            logger.debug("Data received at Server-end: {}".format(frame_client))
            logger.debug("Data received at Client-end: {}".format(client_data))
            assert np.array_equal(client_data, frame_client)
        else:
            # sent frame and data from server to client
            server.send(frame_server, message=target_data)
            # client receives the data and frame and send its data
            server_data, frame_client = client.recv(return_data=target_data)
            # server receives the data and cycle continues
            client_data = server.send(frame_server, message=target_data)
            # check if received frame exactly matches input frame
            assert np.array_equal(frame_server, frame_client)
            # logger.debug data received at client-end and server-end
            logger.debug("Data received at Server-end: {}".format(server_data))
            logger.debug("Data received at Client-end: {}".format(client_data))
            assert client_data == server_data
    except Exception as e:
        if isinstance(e, (ZMQError, ValueError, RuntimeError, queue.Empty)):
            logger.exception(str(e))
        else:
            pytest.fail(str(e))
    finally:
        # clean resources
        if not (stream is None):
            stream.stop()
        if not (server is None):
            server.close()
        if not (client is None):
            client.close()


@pytest.mark.parametrize(
    "pattern, options",
    [
        (0, {"multiserver_mode": True, "multiclient_mode": True}),
        (0, {"multiserver_mode": True}),
        (1, {"multiserver_mode": True, "bidirectional_mode": True}),
    ],
)
def test_multiserver_mode(pattern, options):
    """
    Testing NetGear's Multi-Server Mode with three unique servers
    """
    # initialize
    frame_server = None
    stream = None
    server_1 = None
    server_2 = None
    server_3 = None
    client = None
    # define client-end dict to save frames in-accordance with unique port
    client_frame_dict = {}
    try:
        # open stream
        stream = cv2.VideoCapture(return_testvideo_path())
        # define a single client
        client = NetGear(
            port=["5556", "5557", "5558"],
            pattern=pattern,
            receive_mode=True,
            logging=True,
            **options
        )
        # define three unique server
        server_1 = NetGear(
            pattern=pattern, port="5556", logging=True, **options
        )  # at port `5556`
        server_2 = NetGear(
            pattern=pattern, port="5557", logging=True, **options
        )  # at port `5557`
        server_3 = NetGear(
            pattern=pattern, port="5558", logging=True, **options
        )  # at port `5558`
        i = 0
        while i < random.randint(10, 100):
            (grabbed, frame_server) = stream.read()
            i += 1
        # check if input frame is valid
        assert not (frame_server is None)

        # send frame from Server-1 to client and save it in dict
        server_1.send(frame_server)
        unique_address, frame = client.recv()
        client_frame_dict[unique_address] = frame
        # send frame from Server-2 to client and save it in dict
        server_2.send(frame_server)
        unique_address, frame = client.recv()
        client_frame_dict[unique_address] = frame
        # send frame from Server-3 to client and save it in dict
        server_3.send(frame_server)
        unique_address, frame = client.recv()
        client_frame_dict[unique_address] = frame

        # check if recieved frames from each unique server exactly matches input frame
        for key in client_frame_dict.keys():
            assert np.array_equal(frame_server, client_frame_dict[key])

    except Exception as e:
        if isinstance(e, (ZMQError, ValueError, RuntimeError)):
            logger.exception(str(e))
        else:
            pytest.fail(str(e))
    finally:
        # clean resources
        if not (stream is None):
            stream.release()
        if not (server_1 is None):
            server_1.close()
        if not (server_2 is None):
            server_2.close()
        if not (server_3 is None):
            server_3.close()
        if not (client is None):
            client.close()


@pytest.mark.parametrize("pattern", [0, 1])
def test_multiclient_mode(pattern):
    """
    Testing NetGear's Multi-Client Mode with three unique clients
    """
    # define and activate Multi-Client Mode
    options = {
        "multiclient_mode": True,
        "bidirectional_mode": True,
    }  # bidirectional_mode is activated for testing only

    # initialize
    frame_client = None
    stream = None
    server = None
    client_1 = None
    client_2 = None
    client_3 = None
    try:
        # open network stream
        options_gear = {"THREAD_TIMEOUT": 300}
        stream = VideoGear(source=return_testvideo_path(), **options_gear).start()
        # define single server
        server = NetGear(
            pattern=pattern, port=["5556", "5557", "5558"], logging=True, **options
        )
        # define a three unique clients
        client_1 = NetGear(
            port="5556", pattern=pattern, receive_mode=True, logging=True, **options
        )
        client_2 = NetGear(
            port="5557", pattern=pattern, receive_mode=True, logging=True, **options
        )
        client_3 = NetGear(
            port="5558", pattern=pattern, receive_mode=True, logging=True, **options
        )
        i = 0
        while i < random.randint(10, 100):
            frame_client = stream.read()
            i += 1
        # check if input frame is valid
        assert not (frame_client is None)

        # send frame from 1 server to multiple clients
        server.send(frame_client)
        frame_1 = client_1.recv()
        server.send(frame_client)
        frame_2 = client_2.recv()
        server.send(frame_client)
        frame_3 = client_3.recv()

        # check if received frames from server exactly matches input frame
        assert np.array_equal(frame_1, frame_client)
        assert np.array_equal(frame_2, frame_client)
        assert np.array_equal(frame_3, frame_client)

    except Exception as e:
        if isinstance(e, (ZMQError, ValueError, RuntimeError, queue.Empty)):
            logger.exception(str(e))
        else:
            pytest.fail(str(e))
    finally:
        # clean resources
        if not (stream is None):
            stream.stop()
        if not (server is None):
            server.close()
        if not (client_1 is None):
            client_1.close()
        if not (client_2 is None):
            client_1.close()
        if not (client_3 is None):
            client_1.close()


@pytest.mark.parametrize(
    "options",
    [
        {"max_retries": -1, "request_timeout": 3},
        {"max_retries": 2, "request_timeout": 4, "bidirectional_mode": True},
        {"max_retries": 2, "request_timeout": 4, "multiclient_mode": True},
        {"max_retries": 2, "request_timeout": 4, "multiserver_mode": True},
    ],
)
def test_client_reliablity(options):
    """
    Testing validation function of WebGear API
    """
    client = None
    try:
        # define params
        client = NetGear(
            pattern=1,
            port=[5587] if "multiserver_mode" in options.keys() else 6657,
            receive_mode=True,
            logging=True,
            **options
        )
        # get data without any connection
        frame_client = client.recv()
        # check for frame
        if frame_client is None:
            raise RuntimeError
    except Exception as e:
        if isinstance(e, (RuntimeError)):
            pytest.xfail("Reconnection ran successfully.")
        else:
            logger.exception(str(e))
    finally:
        # clean resources
        if not (client is None):
            client.close()


@pytest.mark.parametrize(
    "options",
    [
        {"max_retries": 2, "request_timeout": 4, "bidirectional_mode": True},
        {"max_retries": 2, "request_timeout": 4, "multiserver_mode": True},
        {"max_retries": 2, "request_timeout": 4, "multiclient_mode": True},
    ],
)
def test_server_reliablity(options):
    """
    Testing validation function of WebGear API
    """
    server = None
    stream = None
    try:
        # define params
        server = NetGear(
            pattern=1,
            port=[5585] if "multiclient_mode" in options.keys() else 6654,
            logging=True,
            **options
        )
        stream = cv2.VideoCapture(return_testvideo_path())
        i = 0
        while i < random.randint(10, 100):
            (grabbed, frame_server) = stream.read()
            i += 1
        # check if input frame is valid
        assert not (frame_client is None)
        # send frame without connection
        server.send(frame_client)
        server.send(frame_client)
    except Exception as e:
        if isinstance(e, (RuntimeError)):
            pytest.xfail("Reconnection ran successfully.")
        else:
            logger.exception(str(e))
    finally:
        # clean resources
        if not (stream is None):
            stream.release()
        if not (server is None):
            server.close()

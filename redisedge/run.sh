#!/bin/bash

../redis/pipert/redis-server --loadmodule ../redisai/build/redisai.so --loadmodule ../redistimeseries/pipert/redistimeseries.so --loadmodule ../redisgears/redisgears.so

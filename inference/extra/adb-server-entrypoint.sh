#!/bin/bash

# start the server
startServer() {
  adb -P 5037 kill-server
  sleep 1
  adb -a -P 5037 start-server
}

# handle interrupts
exit() {
  exit 0
}
trap exit SIGINT SIGTERM

# check server status every second
while true; do
  if ! nc -z localhost 5037; then
    echo "ADB server is not running. Restarting..."
    startServer
  fi
  sleep 1
done

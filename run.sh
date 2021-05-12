#!/bin/bash

# If file based logging is desired, use 
# LOG_TO_FILE=/path/to/file run.sh

IMAGE_NAME=${IMAGE_NAME:=python/swampyer}
CONTAINER_NAME=${CONTAINER_NAME:=swampyer}

help () {
cat << HELP
Usage: run.sh [COMMAND] [ARGUMENTS]...
Performs various for nexus servers including building images, launching and debugging support

COMMANDS:

  If no command is provided, the script will build, configure, and launch an instance of
    the nexus container.

  help
        This help text

  build
        Forces a build of the container

  stop
        docker stop $CONTAINER_NAME

  here
        This will launch the nexus in the current environment without using docker
        Useful when you're in the container itself or are developing locally

  login
        This runs docker exec -ti $CONTAINER_NAME bash to allow "logging in" to a container
      
  root
        This runs docker exec -ti -u root $CONTAINER_NAME bash to allow "logging in" to a
            container as root

  If the command does not match any of the listed commands, the system will instantiate the
  container then pass the entire set of arguments to be invoked in the new container.

HELP
}

build_docker_image () {
  echo "Creating the ${IMAGE_NAME} docker image"
  docker build -t $IMAGE_NAME .
}

upsert_docker_image () {
  if [[ "$(docker images -q ${IMAGE_NAME} 2> /dev/null)" == "" ]]; then
    build_docker_image
  fi
}

default_invoke_command () {
  INVOKE_COMMAND="/app/docker/tox.sh"
}

launch_container () {
  text=$(sed 's/[[:space:]]\+/ /g' <<< ${INVOKE_COMMAND})
  echo "Invoking: ${text}"

  docker run --name $CONTAINER_NAME \
      -ti \
      -v `pwd`:/app \
      -p $PORT_PLAINTEXT:8282 \
      -p $PORT_SSL:8181 \
      --rm \
      $IMAGE_NAME $INVOKE_COMMAND && \
    echo "Started ${CONTAINER_NAME}."
}

login() {
  if [[ "$(docker inspect ${CONTAINER_NAME} 2> /dev/null)" == "[]" ]]; then
    upsert_docker_image
    INVOKE_COMMAND="/app/docker/shell.sh"
    launch_container
  else
    docker exec -ti $CONTAINER_NAME "/app/docker/shell.sh"
  fi
}


if [ $# -eq 0 ]; then
  upsert_docker_image
  default_invoke_command
  launch_container
else
  case $1 in
    -h) help
        ;;
    --help) help
        ;;
    help) help
        ;;

    build) build_docker_image
        ;;

    stop) docker stop $CONTAINER_NAME
        ;;

    here) default_invoke_command
          cd /app/nexus/data
          $INVOKE_COMMAND
        ;;

    login) login
        ;;

    root) docker exec -ti -u root $CONTAINER_NAME /bin/bash
        ;;

    *) upsert_docker_image
       INVOKE_COMMAND="$@"
       launch_container
       ;;
  esac
fi


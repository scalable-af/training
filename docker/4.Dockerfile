FROM alpine

# Currently wget is distributed by default with alpine, curl is not
RUN wget -qO- https://get.docker.com | /bin/sh

# Again we are assuming the script runs successfully even if it does not in this particular example

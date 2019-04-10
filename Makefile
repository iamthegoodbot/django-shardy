clean:
	find . -type f -name "*.py[co]" -delete

prepare: clean


STOP_TARGET := $(shell docker ps -a -q)
stop:
	echo "$(STOP_TARGET)" | xargs docker stop && docker system prune -f


RMI_TARGET := $(shell docker images | grep "none" | awk '/ / { print $$3 }')
rmi:
	echo "$(RMI_TARGET)"| xargs docker rmi -f


build: prepare
	docker build -f Dockerfile -t django_shardy:0.0.2 .


run_bash:
	docker-compose -f docker-compose.yml run --rm app bash


test:
	docker-compose up --abort-on-container-exit

FROM cr.yandex/crpn77gk88olee3rn6ke/saiplay/python.baseimage:0.0.2

RUN mkdir -p /var/log/app && mkdir -p /app

WORKDIR /app

COPY req.txt /app/
COPY req_dev.txt /app/

RUN pip3 install -r req.txt && pip3 install -r req_dev.txt

RUN echo 'alias pycclean="find . -type f -name \"*.py[co]\" -delete"' >> ~/.bashrc && \
    echo 'alias prepare="cd /app && python setup.py develop && cd example/simple/ && python manage.py migrate"' >> ~/.bashrc


COPY ./ /app/

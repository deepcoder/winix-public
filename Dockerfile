# winix-01
# 202011051733

FROM python:3
ENV PIP_NO_CACHE_DIR=1

#ADD /home/user/winix/winix-01.py /home/user/winix

RUN useradd -m -r -u 1000 user && \
    chown user /

USER user
ENV PATH $PATH:/home/user/.local/bin

RUN pip install -U \
    pip \
    setuptools \
    wheel

RUN /usr/local/bin/python -m pip install --upgrade pip

COPY requirements.txt ./
RUN pip install -r requirements.txt

STOPSIGNAL SIGINT

CMD [ "python", "/home/user/winix/winix-01.py" ]


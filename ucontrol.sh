#!/bin/bash

cd '/home/pc-ibr-linux/meus_apps/14.3_U-Control'


# Ativa o ambiente virtual
source '/home/pc-ibr-linux/meus_apps/14.3_U-Control'

ip addr show | grep 'inet ' | awk '{print $2}' | cut -d/ -f1

# Executa o script Python usando Python
python3 main.py


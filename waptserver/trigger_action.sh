#!/bin/bash
sudo -u wapt PYTHONHOME=/opt/wapt PYTHONPATH=/opt/wapt /opt/wapt/bin/python /opt/wapt/waptserver/trigger_action.py $@

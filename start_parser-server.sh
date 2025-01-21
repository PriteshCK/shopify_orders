#!/bin/bash

/root/browser/browser-venv/bin/python /home/browser/shopify_orders/shopify_email_parser.py &
/root/browser/browser-venv/bin/python -m http.server 8081

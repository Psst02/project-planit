import uuid

from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, redirect, session, flash, url_for
from helpers import login_required, show_error, get_db, choose_activities, removal_check, responses_check

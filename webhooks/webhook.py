from flask import Flask, request, jsonify
from datetime import datetime
from config import APPLICATION_TOKEN
from bitrix24_api import call_api
import pytz
from database import get_db  # Импортируем get_db из database.py
from utils import *
from sqlalchemy.orm import Session

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    content_type = request.headers.get('Content-Type')

    # Extract the application token from the request data
    data = None
    if content_type == 'application/json':
        data = request.get_json()
    elif content_type == 'application/x-www-form-urlencoded':
        data = request.form.to_dict()
    else:
        return jsonify({'status': 'unsupported content type'}), 400

    # Check if application_token is present and valid
    application_token = data.get('auth[application_token]')
    if application_token != APPLICATION_TOKEN:
        return jsonify({'status': 'forbidden', 'error': 'Invalid application token'}), 403

    # Get the event type
    event = data.get('event')

    # Create a new session for database operations
    db = next(get_db())

    try:
        # Process the event for adding a new deal
        if event == 'ONCRMDEALADD':
            deal_id = data.get('data[FIELDS][ID]')
            
            # Get deal data
            deal_data = get_deal_data(deal_id)

            # Get assigned, creator, and contact details
            assigned_by_id = deal_data.get('ASSIGNED_BY_ID')
            created_by_id = deal_data.get('CREATED_BY_ID')
            contact_id = deal_data.get('CONTACT_ID')
            created_time = datetime.now(pytz.timezone('Europe/Moscow')).isoformat()

            if assigned_by_id and created_by_id:
                # If there is a transfer of client, fix the time and add to diff_assigment_id table
                if assigned_by_id != created_by_id:
                    fixed_time = datetime.now(pytz.timezone('Europe/Moscow')).isoformat()
                    # Check if the deal already exists in diff_assigment_id
                    existing_diff = db.query(DiffAssignmentID).filter(DiffAssignmentID.deal_id == deal_id).first()
                    if not existing_diff:
                        new_diff_assignment = DiffAssignmentID(deal_id=deal_id, fixed_time=fixed_time, checked=False)
                        db.add(new_diff_assignment)

                # Add deal data to all_created_deal table
                new_deal = AllCreatedDeal(deal_id=deal_id, contact_id=contact_id, created_time=created_time)
                db.add(new_deal)

            db.commit()

        # Process the event for updating a deal
        elif event == 'ONCRMDEALUPDATE':
            deal_id = data.get('data[FIELDS][ID]')
            
            # Get deal data
            deal_data = get_deal_data(deal_id)
            assigned_by_id = deal_data.get('ASSIGNED_BY_ID')
            created_by_id = deal_data.get('CREATED_BY_ID')
            contact_id = deal_data.get('CONTACT_ID')

            # Check conditions for adding to diff_assigment_id table
            if assigned_by_id and created_by_id:
                if assigned_by_id != created_by_id:
                    # Check if the deal exists in all_created_deal
                    existing_deal = db.query(AllCreatedDeal).filter(AllCreatedDeal.deal_id == deal_id).first()
                    
                    # If conditions are met and the deal does not exist in diff_assigment_id, record the time and add data
                    if existing_deal:
                        existing_diff = db.query(DiffAssignmentID).filter(DiffAssignmentID.deal_id == deal_id).first()
                        if not existing_diff:
                            fixed_time = datetime.now(pytz.timezone('Europe/Moscow')).isoformat()
                            new_diff_assignment = DiffAssignmentID(deal_id=deal_id, fixed_time=fixed_time, checked=False)
                            db.add(new_diff_assignment)

            # If the deal has a contact_id, update the record in all_created_deal
            if contact_id:
                existing_contact = db.query(AllCreatedDeal).filter(AllCreatedDeal.deal_id == deal_id).first()
                # If the record exists and the contact is different, update the contact_id
                if existing_contact and existing_contact.contact_id != contact_id:
                    existing_contact.contact_id = contact_id

            db.commit()

    except Exception as e:
        db.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        db.close()

    return jsonify({'status': 'ok'})

def get_deal_data(deal_id):
    """
    Retrieves deal data by its ID.
    """
    # Bitrix24 API method to get deal data
    method = 'crm.deal.get'
    
    # Parameters for the request (deal ID)
    params = {
        'id': deal_id
    }

    # Call the API and retrieve data
    response = call_api(method, params)

    # Assume the response contains a 'result' key with deal data
    if response and 'result' in response:
        return response['result']
    else:
        # In case of error or missing data, return None or an empty dict
        return {}

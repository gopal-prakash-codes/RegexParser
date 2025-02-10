import uuid
import requests
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, flash
from pymongo import MongoClient

app = Flask(__name__)

app.config['SECRET_KEY'] = 'mysecret'

# Connect to MongoDB
client = MongoClient('mongodb://localhost:27017/')
preprocessing_db = client['preprocessing_db']  
preprocessing = preprocessing_db['preprocessing']

postprocessing_db = client['postprocessing_db']  
regex_parser_coll =  postprocessing_db['regex_parser']


@app.route('/', methods=['GET'])
def search():
    search_query = request.args.get('search_query')

    if search_query:
        page = int(request.args.get('page', 1))
        per_page = 10
        start_index = (page - 1) * per_page
        try:
            parser = regex_parser_coll.find_one({'searched_url_pattern': search_query})
        except AttributeError:
            parser = None
        if not parser:
            regex_parser_coll.insert_one({
                'regex_parser_id':  str(uuid.uuid4()),
                'searched_url_pattern': search_query,
                'applied_regex': []
            })
        
        fields_to_search = ['source_domain_name', 'source_full_url']

        pipeline = [
            {
                "$match": {
                    "$or": [
                        {field: {"$regex": search_query, "$options": "i"}} 
                        for field in fields_to_search
                    ]
                }
            },
            {"$addFields": {"truncated_raw_text": {"$substr": ["$raw_text", 0, 100]}}},
            {"$facet": {
                "results": [
                    {"$skip": start_index},
                    {"$limit": per_page}
                ],
                "totalCount": [
                    {"$count": "total"}
                ]
            }}
        ]

        results = list(preprocessing.aggregate(pipeline))
        search_results = results[0]['results']
        total_count = results[0]['totalCount'][0]['total'] if results[0]['totalCount'] else 0

        total_pages = (total_count + per_page - 1) // per_page

       
        return render_template('index.html', results=search_results, searched_pattern=search_query, page=page, total_pages=total_pages)
    else:
        return render_template('index.html', results='search')


@app.route('/regex-parser/<preprocessing_id>')
def regex_parser(preprocessing_id):
    result = preprocessing.find_one({'preprocessing_id': preprocessing_id})
    if not result:
        flash(message="Record not found!", category='error')
        return jsonify({"message": "Record not found!"}), 404

    try:
        raw_text = json.loads(result['raw_text'])
    except json.decoder.JSONDecodeError as e:                               # For Comppass Data
        if str(e) == 'Extra data: line 1 column 13 (char 12)':
            result['raw_text'] = '{' + result['raw_text'] + '}' +'}' 
            raw_text = json.loads(result['raw_text'])       
    

    if type(raw_text) == dict:
        for key in raw_text:
            try:
                data = json.loads(raw_text[key])
                if type(data) == dict:                          # For Realtors data
                    data = [data]
                raw_text[key]  = data
            except TypeError:                                   
                if key in ['lolResults', 'nearbyResults', 'mapResults']:   # For Compass  first type
                    if len(raw_text[key].get('data')) != 0:
                        for text in raw_text[key].get('data'):
                            if not text.get('id'):
                                text['id'] = uuid.uuid4()
                    raw_text[key] = raw_text[key].get('data')
                
                elif type(raw_text[key]) == dict:         # For Redfin data         
                    if not raw_text[key].get('id'):
                        raw_text[key]['id'] = uuid.uuid4()
                    raw_text[key]  = [raw_text[key]]
                elif type(raw_text[key]) == list:
                    for record in raw_text[key]:
                        if not record.get('id'):
                            record['id'] = uuid.uuid4()
                else:
                    pass    

    elif type(raw_text) == list:     # For Compass  first type
        for text in raw_text:
            text['id'] = uuid.uuid4()
        raw_text = {"data" : raw_text}
          
    
    
    result['raw_text']  = raw_text
    result.pop('_id', None)
    
    return render_template('regex-parser.html', result=result)


@app.route('/save-regex', methods=['POST'])
def update_regex_parser():
    applied_regex = request.json['applied_regex']
    searched_url_pattern = request.json["searched_url_pattern"]

    existing_parser = regex_parser_coll.find_one({'searched_url_pattern': searched_url_pattern})
    if existing_parser is None:
        flash(message="Incorrct url!", category='error')
        return jsonify({"message": "Incorrct URL!"}), 400
    
    if not (applied_regex in existing_parser['applied_regex']):
        regex_parser_coll.update_one(
            {'_id': existing_parser["_id"]},
            {'$push': {'applied_regex': applied_regex}}
        )

    return jsonify({"message": "Regex saved successfully!"})


@app.route('/parse-json', methods=['POST'])
def get_json_data():
    preprocessing_id = request.json['preprocessing_id']
    result = preprocessing.find_one({'preprocessing_id': preprocessing_id})
    if not result:
        flash(message="Record not found!", category='error')
        return jsonify({"message": "Record not found!"}), 404
    
    result.pop('_id', None)
    raw_text = json.loads(result['raw_text'])
    agents = json.loads(raw_text['agents'])
    raw_text['agents']  = agents
    result['raw_text']  = raw_text
    
    return jsonify(result)


@app.route('/save-data', methods=['POST'])
def save_to_postprocessing():
    source_url = request.json['source_url']
    source_domain = request.json['source_domain']
    #field_name = request.json['field_name']
    field_value = request.json['field_value']

    if source_domain == 'www.realtor.com':
        data = json.loads(field_value)
    
        address_data  = {}
        people_data = {}
        address = data.get('address',None)
        
        address_data['address_id'] = str(uuid.uuid4())
        address_data['place_name'] = data.get('office', '').get('name', '')
        address_data['city'] = address.get('city', '')
        address_data['street_number'] = address.get('line', '').split()[0] if address.get('line', '') else ''
        address_data['street_name'] = ' '.join(address.get('line').split()[1:]) if address.get('line', '') else ''
        address_data['zip_code'] = address.get('postal_code', '')
        address_data['state'] = address.get('state_code', '')
        address_data['street_pre_directional'] = address.get('street_pre_directional', '')
        address_data['street_suffix'] = address.get('street_suffix', address_data.get('street_name', '').split()[-1][:2] if address_data.get('street_name', '') else None)
        address_data['street_post_directional'] = address.get('street_post_directional', '')
        address_data['unit_type'] = address.get('unit_type', '')
        address_data['unit_number'] = address.get('unit_number', '')
        address_data['county'] = address.get('county', '')
        address_data['county_id_number'] = address.get('county_id_number', '')
        address_data['zip_plus'] = address.get('zip_plus','')
        address_data['source_url'] = source_url
        address_data['source_domain'] = source_domain
        address_data['created_at'] = datetime.now().isoformat()
        address_data['last_modified'] = datetime.now().isoformat()

        #address_obj = postprocessing_db.addressitem.insert_one(address_data)
        address_response = requests.post("http://192.168.20.100:50002/api/v1/address/", json=address_data)
        #print("ADDRESS", address_obj.inserted_id)
        if address_response.status_code == 200:
            print("Address created successfully.", address_response.json())
            people_data = {
                'agent_uuid': str(uuid.uuid4()),
                'person_id': data.get('id'),
                'personal_details': {
                    'first_name': data.get('first_name', ''),
                    'middle_name': data.get('middle_name', ''),
                    'last_name': data.get('last_name', ''),
                    'nickname': data.get('nick_name',''),
                    'date_of_birth': data.get('date_of_birth', ''),
                    'gender': data.get('gender', '')
                },

                'contact_info': {
                    'phone': data.get('phones', ''),
                    'email': data.get('email', '')
                },

                'roles': {
                    'role': data.get('role'),
                    'start_date':  str(data.get('first_month')) + "-"  + str(data.get('first_year')),
                    'end_date': data.get('last_year', '') or data.get('end_date', '')
                },

                'licenses': {
                    'national': {
                        'license_type': data.get('mls', '')[0].get('type', '') if data.get('mls', '') else '',
                        'number': data.get('nrds_id', ''),
                        'issued_by': 'NAR',
                        'valid_until': data.get('valid_until', '')
                    }
                },

                "media": {
                    "media_uuid": str(uuid.uuid4()),
                    "description": data.get('description', ''),
                    "social_media": data.get('social_media', ''),
                    "photos": data.get('photo', ''), 
                    "video": data.get('video', '')
                },

                'source_url': source_url,
                'source_domain': source_domain,
                'created_at': datetime.now().isoformat(),
                'last_modified': datetime.now().isoformat(),
                'addresses_linked': {
                    'address_id': address_data.get('address_id'),
                    'address_type': 'office'
                }
            }

            people_response = requests.post("http://192.168.20.100:50002/api/v1/people/", json=people_data)
            if people_response.status_code == 200:
                print(people_response.json())
            else:
                print("Failed to create People:", people_response.status_code)

        else:
            print("Failed to create address:", address_response.status_code)


    elif source_domain == 'www.redfin.com':

        data = field_value 
        address_data = {}
        property_data = {}
        media_data = {}

        address_data = {
            "address_id": str(uuid.uuid4()),  
            "place_name": data['addressSectionInfo'][0]['streetAddress'].get('assembledAddress',''),
            "street_number": data['addressSectionInfo'][0]['streetAddress'].get('streetNumber',''),
            "street_pre_directional": data['addressSectionInfo'][0]['streetAddress'].get('directionalPrefix', ''),  
            "street_pos_directional": data['addressSectionInfo'][0]['streetAddress'].get('directionalSuffix',''),
            "street_name": data['addressSectionInfo'][0]['streetAddress'].get('streetName',''),
            "unit_type": data['addressSectionInfo'][0]['streetAddress'].get('unitType', ''),
            "unit_number": data['addressSectionInfo'][0]['streetAddress'].get('unitValue',''),
            "city": data['addressSectionInfo'][0].get('city',''),
            "county": data['addressSectionInfo'][0].get('countryCode',''),  
            "county_id_number": data['addressSectionInfo'][0].get('county_id_number',''),  
            "state": data['addressSectionInfo'][0].get('state',''),
            "zip_code": data['addressSectionInfo'][0].get('zip',''),
            "zip_plus": "",  
            "latitude": str(data['addressSectionInfo'][0]['latLong']['latitude']),
            "longitude": str(data['addressSectionInfo'][0]['latLong']['longitude']),
            "source_url": source_url,  
            "source_domain": source_domain,  
            "created_at": datetime.now().isoformat(), 
            "last_modified": datetime.now().isoformat(),
        }
        address_response = requests.post("http://192.168.20.100:50002/api/v1/address/", json=address_data)
        if address_response.status_code == 200:
            print("Address created successfully.", address_response.json())
            property_data = {
                "address_id": address_data.get('address_id'),
                "property_id": str(uuid.uuid4()),
                "source_url": source_url,  
                "source_domain": source_domain,  
                "created_at": datetime.now().isoformat(), 
                "last_modified": datetime.now().isoformat(),
                "bedroom_count": str(data['addressSectionInfo'][0].get('beds', '')),
                "bathrooms": str(data['addressSectionInfo'][0].get('baths', '') or data['addressSectionInfo'][0].get('numFullBaths', '')),
                "unit_count": data['addressSectionInfo'][0]['streetAddress'].get('unitValue',''),
                "garage": "",
                "square_footage": str(data['addressSectionInfo'][0]['sqFt'].get('value','')),
                "lot_size": "",
                "year_built": str(data['addressSectionInfo'][0].get('yearBuilt', '')),
                "property_type": str(data['addressSectionInfo'][0].get('propertyType')),
                "heating_type": "",
                "cooling_type": "",
                "roof_type": "",
                "foundation_type": "",
                "exterior_material": "",
                "pool": "",
                "zoning_classification": "",
                "hoa_fees": "",
                "accessibility_features": "",
                'appliances_included':"",
                'association': "",
                'guest_accommodation_description': "",
                'waterfront_features': "",
                "additional_parcels": "",
                "community_features": "",
                "construction_materials": "",
                "county": "",
                "covered_spaces": "",
                "direction_property_faces": "",
                "disclosures": "",
                "elementary_school": "",
                "estimated_taxes": "",
                "exterior_features": "",
                "fema_floodplain_status": "",
                "fencing": "",
                "fireplaces_total": "",
                "flooring_types": "",
                "foundation_details": "",
                "green_energy_efficient_features": "",
                "green_sustainability_features": "",
                "guest_acommodation_description": "",
                "high_school": "",
                "horse_amenities": "",
                "horse_property": "",
                "idx_opt_in": "",
                "interior_features": "",
                "internet_address_display": "",
                "internet_automated_valuation_display": "",
                "internet_consumer_comment": "",
                "internet_entire_listing_display": "",
                "laundry_location": "",
                "levels": "",
                "list_agent_information": "",
                "listing_contract_date": "",
                "listing_id": "",
                "list_office_information": "",
                "list_price": "",
                "living_area": "",
                "living_area_source": "",
                "lot_features": "",
                "main_level_bedrooms": "",
                "middle_or_junior_school": "",
                "mls_area_major": "",
                "mls_status": "",
                "new_construction": "",
                "number_of_dining_areas": "",
                "number_of_living_areas": "",
                "open_house_count": "",
                "parcel_number": "",
                "parking_features": "",
                "parking_total": "",
                "patio_and_porch_features": "",
                "pool_features": "",
                "private_pool": "",
                "property_condition": "",
                "property_sub_type": "",
                "public_remarks": "",
                "sewer_type": "",
                "spa_features": "",
                "special_listing_conditions": "",
                "subdivision_name": "",
                "syndicate_to": "",
                "syndication_remarks": "",
                "tax_assessed_value": "",
                "tax_legal_description": "",
                "tax_map_number": "",
                "tax_year": "",
                "unit_style": "",
                "utilities": "",
                "view": "",
                "virtual_tour": "",
                "waterfront": "",
                "water_source": "",
                "window_features": "",
                "year_built_source": ""
            }  
            property_response = requests.post("http://192.168.20.100:50002/api/v1/property/", json=property_data)
            if property_response.status_code == 200:
                print(property_response.json())
                media_data = {
                    "media_id": str(uuid.uuid4()),
                    "property_id": property_data['property_id'],
                    "source_url": source_url,  
                    "source_domain": source_domain,  
                    "created_at": datetime.now().isoformat(), 
                    "last_modified": datetime.now().isoformat(),
                    "photos": [
                        {
                          "photoUrls": {
                            "nonFullScreenPhotoUrlCompressed": data['mediaBrowserInfo'][0]["photos"][0]["photoUrls"].get("nonFullScreenPhotoUrlCompressed"),
                            "nonFullScreenPhotoUrl": data['mediaBrowserInfo'][0]["photos"][0]["photoUrls"].get("nonFullScreenPhotoUrl"),
                            "fullScreenPhotoUrl": data['mediaBrowserInfo'][0]["photos"][0]["photoUrls"].get("fullScreenPhotoUrl"),
                            "lightboxListUrl": data['mediaBrowserInfo'][0]["photos"][0]["photoUrls"].get("lightboxListUrl")
                          },
                          "thumbnailData": {
                            "thumbnailUrl": data['mediaBrowserInfo'][0]["photos"][0]["thumbnailData"].get("thumbnailUrl")
                          },
                          "displayLevel": data['mediaBrowserInfo'][0]["photos"][0].get("displayLevel"),
                          "dataSourceId": data['mediaBrowserInfo'][0]["photos"][0].get("dataSourceId"),
                          "photoType": data['mediaBrowserInfo'][0]["photos"][0].get("photoType"),
                          "subdirectory": data['mediaBrowserInfo'][0]["photos"][0].get("subdirectory"),
                          "fileName": data['mediaBrowserInfo'][0]["photos"][0].get("fileName"),
                          "height": data['mediaBrowserInfo'][0]["photos"][0].get("height"),
                          "width": data['mediaBrowserInfo'][0]["photos"][0].get("width"),
                          "photoId": data['mediaBrowserInfo'][0]["photos"][0].get("photoId")
                        }
                    ],
                    "videos": data['mediaBrowserInfo'][0].get("videos"),
                    "streetView": {
                      "latLong": data['mediaBrowserInfo'][0]["streetView"].get("latLong"),
                      "streetViewURL": data['mediaBrowserInfo'][0]["streetView"].get("streetViewUrl"),
                      "staticMapURL": data['mediaBrowserInfo'][0]["streetView"].get("staticMapUrl")
                    },
                    'agent_media':'',
                    'broker_media':{},
                    'office_media': {},
                    'downloaded': '',
                    'local_path': '',
                    'file_type': '',
                    'file_size': '',
                    'order_number': '',
                    'related_to': {}
                }

                media_response = requests.post("http://192.168.20.100:50002/api/v1/media/", json=media_data)
                if media_response.status_code == 200:
                    print("MEDIA", media_response.json())
                else:
                    print("Failed to create Media:")
            else:
                print("Failed to create Property:", property_response.status_code)
        else:
            print("Failed to create address:", address_response.status_code)
    
    elif source_domain == 'www.compass.com':
        data = json.loads(field_value)
        print("SDFSDFSDF",data)                   #Extract/separate the data from compass source to send it to postprocessing collection
    

    flash(message="Data saved successfully!", category='success')    
    
    return jsonify({"message":"Successful"})
    

@app.route('/inserted-data', methods=['GET'])
def show_data():
    all_data = list(postprocessing_db.peopleitem.find())
    all_response_data = []
    for data in all_data:
        response_data={
            'people_collection_data': data, 
            'mediad_collection_data': postprocessing_db.mediaitem.find_one({'_id': data.get('media_linked')}),
            'property_collection_data': postprocessing_db.propertyitem.find_one({'_id': data.get('property_linked')}),
            'realtor_collection_data': postprocessing_db.realtoritem.find_one({'_id': data.get('realtor_linked')}),
        }
        response_data['address_collection_data'] = postprocessing_db.addressitem.find_one({'_id': response_data['property_collection_data'].get('address_id')})
        print(response_data['address_collection_data'])

        response_data['people_collection_data']['_id'] = str(response_data['people_collection_data']['_id'])
        response_data['mediad_collection_data']['_id'] = str(response_data['mediad_collection_data']['_id'])
        response_data['property_collection_data']['_id'] = str(response_data['property_collection_data']['_id'])
        response_data['address_collection_data']['_id'] = str(response_data['address_collection_data']['_id'])
        response_data['realtor_collection_data']['_id'] = str(response_data['realtor_collection_data']['_id'])

        response_data['people_collection_data']['media_linked'] = str(response_data['people_collection_data']['media_linked'])
        response_data['people_collection_data']['property_linked'] = str(response_data['people_collection_data']['property_linked'])
        response_data['people_collection_data']['realtor_linked'] = str(response_data['people_collection_data']['realtor_linked'])
        response_data['property_collection_data']['address_id'] = str(response_data['property_collection_data']['address_id'])
        

        all_response_data.append(response_data)
        
    

    return render_template('inserted_records.html', results=all_response_data)


if __name__ == "__main__":
    app.run(debug=True, port=5002, host='0.0.0.0')

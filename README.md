# M-Pesa Integration with Daraja API

This guide provides a comprehensive walkthrough for integrating M-Pesa payment services using Safaricom's Daraja API.

## Table of Contents
1. [Getting Started](#getting-started)
2. [Authorization API](#authorization-api)
3. [M-Pesa Express API (STK Push)](#m-pesa-express-api-stk-push)
4. [Handling STK Push Callbacks](#handling-stk-push-callbacks)
5. [Querying STK Push Status](#querying-stk-push-status)
6. [Common Errors](#common-errors)

## Getting Started

1. Go to [Daraja Portal](https://developer.safaricom.co.ke/) and create an account
2. Create an app in the sandbox environment (tick all the boxes)
3. Once registered, your app will appear in the sandbox apps section
4. For production, Safaricom will send a pass key via email after registration

### APIs Available
- Authorization API (required for all other APIs)
- M-Pesa Express API (STK Push)
- C2B API
- B2C API

### Required Credentials
- Consumer Key
- Consumer Secret
- Pass Key

## Authorization API

This API generates a token used to authenticate all other API requests.

```python
import base64
import requests

def generate_access_token():
    consumer_key = "YOUR_CONSUMER_KEY"
    consumer_secret = "YOUR_CONSUMER_SECRET"
    
    # Choose based on your environment
    url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    # For production
    # url = "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    
    try:
        encoded_credentials = base64.b64encode(f"{consumer_key}:{consumer_secret}".encode()).decode()
        
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json"
        }
        
        # Send request and parse response
        response = requests.get(url, headers=headers).json()
        
        # Check for errors and return the access token
        if "access_token" in response:
            return response["access_token"]
        else:
            raise Exception("Failed to get access token: " + response["error_description"])
            
    except Exception as e:
        raise Exception("Failed to get access token: " + str(e))
```

## M-Pesa Express API (STK Push)

This API allows merchants to initiate transactions from online systems. A payment prompt (STK Push) is sent to the customer's phone to complete the payment.

### Process Flow

1. Merchant submits API request with required parameters
2. API receives and validates the request, then sends acknowledgment
3. STK push trigger is sent to customer's M-Pesa registered number
4. Customer confirms by entering their PIN
5. M-Pesa processes the payment:
   - Validates customer's PIN
   - Debits customer's mobile wallet
   - Credits the merchant
6. Results are sent back to the merchant via callback URL
7. Customer receives SMS confirmation

### Implementation

```python
import requests
import base64
from datetime import datetime

def send_stk_push():
    token = generate_access_token()
    
    # Sandbox URL
    url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    # Production URL
    # url = "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Generate timestamp and password
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    shortcode = "174379"  # Your paybill/till number
    passkey = "YOUR_PASSKEY"
    stk_password = base64.b64encode((shortcode + passkey + timestamp).encode()).decode()
    
    request_body = {
        "BusinessShortCode": shortcode,    
        "Password": stk_password,    
        "Timestamp": timestamp,    
        "TransactionType": "CustomerPayBillOnline",  # Use "CustomerBuyGoodsOnline" for Till numbers
        "Amount": "1",    
        "PartyA": "254XXXXXXXXX",  # Customer phone number
        "PartyB": shortcode,    
        "PhoneNumber": "254XXXXXXXXX",  # Customer phone number
        "CallBackURL": "https://mydomain.com/callback",    
        "AccountReference": "Test",  # Identifier for the transaction
        "TransactionDesc": "Test Payment"
    }
    
    response = requests.post(url, json=request_body, headers=headers)
    return response.json()
```

### Request Parameters

| Parameter | Description | Type | Format/Example |
|-----------|-------------|------|----------------|
| BusinessShortCode | Organization's shortcode (Paybill or Buygoods) | Numeric | 5-6 digits, e.g., 174379 |
| Password | Base64 encoded string (Shortcode+Passkey+Timestamp) | String | base64.encode(Shortcode+Passkey+Timestamp) |
| Timestamp | Transaction timestamp | String | YYYYMMDDHHMMSS |
| TransactionType | Identifies transaction type | String | CustomerPayBillOnline or CustomerBuyGoodsOnline |
| Amount | Money that customer pays to shortcode | Numeric | Whole numbers only, e.g., 10 |
| PartyA | Phone number sending money | Numeric | MSISDN (12 digits), e.g., 254XXXXXXXXX |
| PartyB | Organization receiving funds | Numeric | Same as BusinessShortCode |
| PhoneNumber | Mobile number to receive STK prompt | Numeric | MSISDN (12 digits), e.g., 254XXXXXXXXX |
| CallBackURL | URL to receive transaction result notifications | URL | https://mydomain.com/path |
| AccountReference | Transaction identifier (shown to customer) | Alpha-Numeric | Max 12 characters |
| TransactionDesc | Additional information/comment | String | Max 13 characters |

## Handling STK Push Callbacks

After an STK push request, Safaricom sends transaction results to your callback URL.

### Callback URL Requirements
- Must be a valid secure URL (HTTPS)
- For local development, use tools like ngrok to create a tunnel to your localhost

### Sample Callback Data

#### Successful Transaction
```json
{
   "Body": {
      "stkCallback": {
         "MerchantRequestID": "29115-34620561-1",
         "CheckoutRequestID": "ws_CO_191220191020363925",
         "ResultCode": 0,
         "ResultDesc": "The service request is processed successfully.",
         "CallbackMetadata": {
            "Item": [
               {
                  "Name": "Amount",
                  "Value": 1.00
               },
               {
                  "Name": "MpesaReceiptNumber",
                  "Value": "NLJ7RT61SV"
               },
               {
                  "Name": "TransactionDate",
                  "Value": 20191219102115
               },
               {
                  "Name": "PhoneNumber",
                  "Value": 254708374149
               }
            ]
         }
      }
   }
}
```

#### Failed Transaction
```json
{
   "Body": {
      "stkCallback": {
         "MerchantRequestID": "29115-34620561-1",
         "CheckoutRequestID": "ws_CO_191220191020363925",
         "ResultCode": 1032,
         "ResultDesc": "Request canceled by user."
      }
   }
}
```

### Django Implementation Example

```python
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
def mpesa_callback(request):
    callback_data = json.loads(request.body)
    
    result_code = callback_data["Body"]["stkCallback"]["ResultCode"]
    if result_code != 0:
        error_message = callback_data["Body"]["stkCallback"]["ResultDesc"]
        return JsonResponse({"ResultCode": result_code, "ResultDesc": error_message})
    
    metadata = callback_data["Body"]["stkCallback"]["CallbackMetadata"]["Item"]
    
    amount = next(item["Value"] for item in metadata if item["Name"] == "Amount")
    mpesa_receipt = next(item["Value"] for item in metadata if item["Name"] == "MpesaReceiptNumber")
    phone = next(item["Value"] for item in metadata if item["Name"] == "PhoneNumber")
    
    print(f"Transaction Successful: {amount}, {mpesa_receipt}, {phone}")
    
    # Process payment here (update database, etc.)
    
    return JsonResponse({"status": "success"})
```

## Querying STK Push Status

You can check the status of an M-Pesa Express (STK Push) transaction using the query API.

```python
import requests
import base64
from datetime import datetime

def query_stk_push(checkout_request_id):
    token = generate_access_token()
    
    # Sandbox URL
    url = "https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query"
    # Production URL
    # url = "https://api.safaricom.co.ke/mpesa/stkpushquery/v1/query"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Generate timestamp and password
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    shortcode = "174379"  # Your paybill/till number
    passkey = "YOUR_PASSKEY"
    password = base64.b64encode((shortcode + passkey + timestamp).encode()).decode()
    
    request_body = {
        "BusinessShortCode": shortcode,    
        "Password": password,    
        "Timestamp": timestamp,    
        "CheckoutRequestID": checkout_request_id
    }
    
    response = requests.post(url, json=request_body, headers=headers)
    return response.json()
```

### Sample Response
```json
{
   "ResponseCode": "0",
   "ResponseDescription": "The service request has been accepted successfully",
   "MerchantRequestID": "22205-34066-1",
   "CheckoutRequestID": "ws_CO_13012021093521236557",
   "ResultCode": "0",
   "ResultDesc": "The service request is processed successfully."
}
```

## Common Errors

| Result Code | Description |
|-------------|-------------|
| 0 | Successful transaction |
| 1 | Insufficient funds |
| 1032 | Request cancelled by user |

Other common errors include:
- Incorrect or typo in the URL
- Bad format in request parameters
- Incorrect encoding
- Invalid authentication token
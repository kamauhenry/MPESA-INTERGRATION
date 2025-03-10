from django.shortcuts import render
from .forms import paymentForm
from datetime import datetime
from dotenv import load_dotenv
import os , base64, requests ,re, json
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import crsf_exempt 



#loqding the .env file  
load_dotenv()

#retrieve the secret key from the .env file
CONSUMER_KEY = os.getenv('CONSUMER_KEY')
CONSUMER_SECRET = os.getenv('CONSUMER_SECRET')
MPESA_PASSKEY = os.getenv('MPESA_PASSKEY')
MPESA_SHORTCODE = os.getenv('MPESA_SHORTCODE')
CALLBACK_URL = os.getenv('CALLBACK_URL')
MPESA_BASE_URL = os.getenv('MPESA_BASE_URL')


def generate_access_token():
    
 
    try:
        encoded_credentials=base64.b64encode(f"{CONSUMER_KEY}:{CONSUMER_SECRET}".encode()).decode()
    
        header = {
        "Authorization": f"Basic {encoded_credentials}",
        "content-type": "application/json"
        }
        #send request n parse the response 
        response = requests.get(
            f"{MPESA_BASE_URL}/oasuth/v1/generate? grant_type=client_credentials",
            ).json()

        #check for errors n return the access token
        if "access_token" in response:
            return response["access_token"]
        else: 
            raise Excption("Failed to get acces token:")
    except Exception as e:
        raise Exception("Failed to get acces token:"+str(e))


def send_stk_push():
    try:
        token =  generate_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type" : "application/json"
        }
            

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        stk_password = base64.b64encode({MPESA_SHORTCODE+MPESA_PASSKEY+timestamp}.encode()).decode()

        request_body = {
        "BusinessShortCode": MPESA_SHORTCODE,    
        "Password": stk_password,    
        "Timestamp":timestamp,    
        "TransactionType": "CustomerPayBillOnline",    
        "Amount": amount,    
        "PartyA":phone_number,    
        "PartyB":MPESA_SHORTCODE,    
        "PhoneNumber":phone_number,    
        "CallBackURL": CALLBACK_URL,    
        "AccountReference":"Test",    
        "TransactionDesc":"Test"
        }
        response = request.post(f"{MPESA_BASE_URL}/mpesa/stkpush/v1/processrequest",
            json=request_body,
            headers= headers
        ).json()

        return response
    
    except Exception as e:
        print("Failed to send stk push"+str(e))
        return e

def format_phone_number(phone_number):
    phone_number=phone_number.replace("+","")
    if re.match(r"254\d{9}$",phone_number):
        return phone_number
    elif phone_number.startswith("0") and len(phone_number)==10:
        return "254"+phone_number[1:]
    else:
        raise ValueError("Invalid phone number format")

def payment(request):
    if request.method == 'POST':
        form = paymentForm(request.POST)
        if form.is_valid():
            phone_number = format_phone_number(form.cleaned_data['phone_number'])
            amount = form.cleaned_data['amount']
            paybill = form.cleaned_data['paybill']
            account_number = form.cleaned_data['account_number']
            description = int(form.cleaned_data['description'])
            response = send_stk_push(phone_number,amount)
            print(response)
            if response.get("ResponseCode") == "0":
                checkout_request_id = response["CheckoutRequestID"]
                return render(request, 'pending.html',{"Checkout_request_id":Checkout_request_id})
            else:
                errorMessage = response.get("errorMessage", "Failed to process request")
                return render(request, 'paymentForm.html', {'form': form, 'errorMessage': errorMessage})        
    else:
        form = paymentForm()
    return render(request, 'mpesa_payment/payment.html', {'form': form})

 
@csrf_exempt 
def mpesa_callback(request):
    if request.method != "POST":
        return HttpResponseBadRequest("Only POST requests are allowed")
    
    try:#parse the callback data from therequest body
        callback_data =json.loads(request.body)
        
        #check the result code
        result_code = callback_data["Body"]["stkCallback"]["ResultCode"]
        if result_code != 0:
            #handle unsuccessful transaction
            error_message = callback_data["Body"]["stkCallback"]["ResultCode"]
            return JsonResponse({"ResultCode":result_code, "ResultDesc":error_message})
        
        #extract the metadata from the callback data
        checkout_id = callback_data["Body"]["stkCallback"]["CheckoutRequestID"]
        body = callback_data["Body"]["stkCallback"]["CallbackMetadata"]["Item"]
        
        amount = next(item["value"] for item in body if item ["Name"]=="Amount")
        mpesa_code= next(item["value"] for item in body if item ["Name"]=="MpesaReceiptNumber")
        phone = next(item["value"] for item in body if item ["Name"]=="PhoneNumber")
        
        #save the transaction details to the database
        Transaction.objects.create(
            amount=amount,
            checkout_id,
            mpesa_code=mpesa_code,
            phone_number=phone,
            status="success"
        ),

        #return a success response to M-pesa
        return JsonResponse("success", safe=False)

    except (json.JSONDecodeError, KeyError) as e:
        #Handle error
        return HttpResponseBadRequest("Invalid request body: {str(e)}")


def query_stk_push(checkout_request_id):
    try:
        token = generate_access_token()
                headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password = base64.b64encode(f"{MPESA_SHORTCODE+MPESA_PASSKEY+timestamp}".encode()).decode()

        request_body = {
        "BusinessShortCode": MPESA_SHORTCODE,    
        "Password": password,    
        "Timestamp":timestamp,    
        "CheckoutRequestID": checkout_request_id
        }
        response = request.post(f"{MPESA_BASE_URL}/mpesa/stkpushquery/v1/query", json=request_body,
         headers= headers)
        print(response.json())
    
    except requests.RequestException as e:
        print("Failed to query stk status"+str(e))
        return {"error":str(e)}


#view to query the status of the stk push and return the response to the user
def stk_status_view(request):
    if request.method == "POST":
        try:
            #parse the JSON body
            data = json.loads(request.body)
            checkout_request_id = data.get('checkout_request_id')

            #query the status of the stk push
            status = query_stk_push(checkout_request_id)

            #return the status to the user
            return JsonResponse({"status" : status})
        except json.JSONDecodeError :
            return JsonResponse({"error":"Invalid request body"}, status=400)
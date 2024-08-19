# Taiwa
Meta App for Japanese Sentence Structure Education

## How to Set Up Meta App

1. **Create a Facebook Page**: Create a Facebook Page for Taiwa. This is necessary because Taiwa will be associated with this page.

2. **Create a Facebook App**: Create a Facebook App. This can be done through the Facebook Developers portal. The app will be used to control and manage Taiwa.

3. **Set Up Messenger**: In the Facebook Developers portal, set up Messenger for Taiwa. This involves selecting the page created earlier and generating a token that will be used to authenticate Taiwa.

## How to Test Locally

1. **Install Flask**: Flask can be installed using pip, which is a package manager for Python. Open a terminal and type the following.

```
pip install flask
```

2. **Run the Flask App**: The Flask app can be run by typing the following command in a terminal. By default, the Flask app will run on `localhost` on port `5000`. The terminal will prompt for a verify token. Set one and memorize it. It will be used as the verify token when configuring the Facebook App.

```
python app.py
```

3. **Expose the Local Server to the Internet**: Install ngrok and run it on the same port where the Flask app is running. In a terminal, type the following. ngrok will provide a public URL that will be used as the webhook URL when configuring the Facebook App.

```
ngrok http 5000
```

4. **Set Up a Webhook on Facebook**: Go to the Facebook Developers portal and navigate to the Facebook App. Under 'Products', click on 'Messenger' and then 'Messenger API Settings'. Under 'Configure webhooks', click 'New Subscription'. In the 'Callback URL' field, enter the ngrok URL followed by the endpoint specified in the Flask app (e.g., `https://ngrok-url/webhook`). In the 'Verify Token' field, enter the verify token used in the Flask app. Check the 'messages' and 'messaging_postbacks' boxes under 'Webhook Fields', then click 'Verify and Save'.

5. **Test Taiwa**: Go to the Facebook page associated with Taiwa and click 'Send Message'. Any messages sent here will be sent to Taiwa. If Taiwa is set up correctly, you should see Taiwa's replies appear in the chat.

## How to Deploy Locally on Unix

1. **Install Gunicorn**: Gunicorn can be installed using pip, which is a package manager for Python. Open a terminal and type:

```
pip install gunicorn
```

2. **Run the Flask App with Gunicorn:** In a terminal, navigate to the directory containing the Flask app and type the following. By default, Gunicorn will start serving the app on `localhost` on port `8000`. In the command, `-w 4` specifies that Gunicorn should use 4 worker processes. Adjust this value as necessary for your specific application and environment.

```
gunicorn -w 4 app:app
```
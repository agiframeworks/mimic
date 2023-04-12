import base64, io, os, sys, argparse
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.cloud import speech_v1p1beta1 as speech
from google.cloud import translate_v3 as translate
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def get_gmail_service(api_key_file):
  credentials = service_account.Credentials.from_service_account_file(
    api_key_file, scopes=['https://www.googleapis.com/auth/gmail.modify'])
  return build('gmail', 'v1', credentials=credentials)


def process_audio_file(audio_file, api_key):
  client = speech.SpeechClient(credentials=api_key)
  with io.open(audio_file, "rb") as audio_file:
    content = audio_file.read()
  audio = speech.RecognitionAudio(content=content)
  config = speech.RecognitionConfig(
    encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
    sample_rate_hertz=16000,
    language_code="en-US")
  response = client.recognize(config=config, audio=audio)
  return response.results[0].alternatives[0].transcript


def detect_language(text, api_key):
  client = translate.TranslationServiceClient(credentials=api_key)
  parent = f"projects/{api_key.project_id}/locations/global"
  response = client.detect_language(content=text,
                                    parent=parent,
                                    mime_type="text/plain")
  return response.languages[0].language_code


def translate_text_v3(text, target_language, api_key):
  client = translate.TranslationServiceClient(credentials=api_key)
  parent = f"projects/{api_key.project_id}/locations/global"
  response = client.translate_text(contents=[text],
                                   target_language_code=target_language,
                                   parent=parent,
                                   mime_type="text/plain")
  return response.translations[0].translated_text


def send_email(email_service, user_id, to, subject, message_text):
  message = MIMEMultipart()
  message['To'] = to
  message['Subject'] = subject
  message.attach(MIMEText(message_text))
  raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
  message_body = {'raw': raw_message}
  email_service.users().messages().send(userId=user_id,
                                        body=message_body).execute()


def process_incoming_email(email_service, user_id, message_id, api_key):
  message = email_service.users().messages().get(userId=user_id,
                                                 id=message_id).execute()
  sender = message['payload']['headers'][0]['value']
  subject = f"Transcription: {message['payload']['headers'][1]['value']}"
  attachments = [
    part for part in message['payload']['parts']
    if part['filename'].lower().endswith(('.wav', '.mp3', '.ogg'))
  ]
  if not attachments: return
  for attachment in attachments:
    attachment_id = attachment['body']['attachmentId']
    attachment = email_service.users().messages().attachments().get(
      id=attachment_id, userId=user_id, messageId=message_id).execute()
    audio_data = base64.urlsafe_b64decode(attachment['data'])
    with open('temp_audio_file', 'wb') as f:
      f.write(audio_data)


def main(api_key_file, recipient_email):
  email_service = get_gmail_service(api_key_file)
  user_id = 'me'

  # Fetch the list of emails with attachments
  emails = email_service.users().messages().list(userId=user_id,
                                                 q="has:attachment").execute()

  # Process each email
  for email in emails['messages']:
    process_incoming_email(email_service, user_id, email['id'], api_key_file,
                           recipient_email)


if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument(
    "api_key_file",
    help="Path to the API key file (JSON) for Google Cloud services.")
  parser.add_argument(
    "recipient_email",
    help="Email address to send the transcriptions and original attachments.")
  args = parser.parse_args()

  main(args.api_key_file, args.recipient_email)

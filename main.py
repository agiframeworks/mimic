from email_audio_transcription import main

if __name__ == "__main__":
  api_key_json = os.environ['GOOGLE_API_KEY']
  api_key_dict = json.loads(api_key_json)
  recipient_email = "josh.stephens@gmail.com"
  main(api_key_file, recipient_email)

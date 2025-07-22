import speech_recognition as sr


# code to test the microhones and change the device id in web_ui.py
print(" Available microphones:")
for i, name in enumerate(sr.Microphone.list_microphone_names()):
    print(f"{i}: {name}")

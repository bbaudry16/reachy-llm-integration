import pyttsx3


if __name__ == "__main__":
    engine = pyttsx3.init() # object creation

    # RATE
    rate = engine.getProperty('rate')   # getting details of current speaking rate
    print (rate)                        # printing current voice rate
    engine.setProperty('rate', 125)     # setting up new voice rate

    # VOLUME
    volume = engine.getProperty('volume')   # getting to know current volume level (min=0 and max=1)
    print (volume)                          # printing current volume level
    engine.setProperty('volume',1.0)        # setting up volume level  between 0 and 1

    # VOICE
    voices = engine.getProperty('voices')       # getting details of current voice
    #engine.setProperty('voice', voices[0].id)  # changing index, changes voices. o for male
    

    text = """Bonjour, je m'appelle Reachy et je suis un robot humanoïde développé par Pollen Robotics. Aujourd'hui, nous allons tester les capacités de reconnaissance vocale de mon système. """
    text_eng = """Hello, my name is Reachy and I am a humanoid robot. Today we are testing the speech to text capabilities of my system. """

    for i in range(len(voices)):
        print(i)
        engine.setProperty('voice', voices[i].id)   # changing index, changes voices. 1 for female

        engine.say(text)
        engine.say(text_eng)
        engine.runAndWait()
        engine.stop()
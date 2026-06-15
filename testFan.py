from reachy_sdk import ReachySDK
# Dans un terminal python, après connexion
reachy = ReachySDK(host="10.59.1.20")

# Est-ce que reachy.fans existe ?
print(dir(reachy))
print(reachy.fans)

for name, fan in reachy.fans.items():
    print(name, fan)

reachy.fans.r_shoulder_fan.on()
moderator_roles = ["RT Reporter", "CT Reporter", "RT Updater", "CT Updater", "Developer", "RT Committee",
                   "CT Committee", "Boss"]
                   
with open("sticky_messages.txt") as file:
    r = file.read()
    sticky_message_ids = [int(id) for id in r.split("\n")]

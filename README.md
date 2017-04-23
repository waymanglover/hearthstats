# hearthstats

Scrape Hearthstone decks from HearthPwn (http://hearthpwn.com), then build a
SQLite database of the results. Can also scrape card collection data from
HearthPwn/Innkeeper (http://innkeeper.com), and integrates with omgvamp's
Mashape Hearthstone API (http://hearthstoneapi.com) to build a table of card
data that can be used to make more advanced queries.

Requires lxml, cssselect, and requests packages.
These can be installed by opening a command prompt in the hearthstats folder, and running the following command:

```
pip install -r requirements.txt
```

```
usage: hearth.py [-h] [--buildcards] [--builddecks] [--buildcollection]
                 [--perclass] [--count COUNT] [--filtering FILTERING]
                 [--sorting SORTING] [--patch PATCH] [--results]

Scrape Hearthstone decks from HearthPwn (http://hearthpwn.com), then build a
SQLite database of the results. Can also scrape card collection data from
HearthPwn/Innkeeper (http://innkeeper.com), and integrates with omgvamp's
Mashape Hearthstone API (http://hearthstoneapi.com) to build a table of card
data that can be used to make more advanced queries.

optional arguments:
  -h, --help            show this help message and exit
  --buildcards          build card database from Mashape
  --builddecks          build deck database from HearthPwn
  --buildcollection     build personal card collection from Hearthpwn
  --perclass            get the same number of decks for each class
  --count COUNT         number of decks to retrieve (per class, if --perclass
                        is set)
  --filtering FILTERING
                        the HearthPwn filter used when finding decks, as seen
                        in the HearthPwn URL
  --sorting SORTING     the HearthPwn sorting used when finding decks, as seen
                        in the HearthPwn URL after "&sort="
  --patch PATCH         the HearthPwn patch ID used when finding decks, as
                        seen in the HearthPwn URL after "&filter-build="
  --results             for all cards, display (in a CSV-ish format) the:
                        cardname, hero (or neutral), total count of decks
                        using the card, percentage of decks using the card,
                        average count of the card in decks using it, and the
                        count of the card in your collection.
```

Before populating the card database, you must first register for an API key at 
Mashape.com. Once you have your API key, rename config.ini.example to config.ini if 
config.ini does not already exist, and open config.ini in a text editor 
(running the script once will also create a blank config.ini file):

```
[Configuration]
mashapekey = keygoeshere
authsession = authsessiongoeshere
```

Replace keygoeshere with your Mashape API key.

Before populating the card collection database, you must first sync your card collection 
using Innkeeper. Then, log in to your HearthPwn account. Using your web browser's
development console (or another cookie-viewing tool), get the value of the Auth.Session
cookie. Once you have your Auth.Session value, rename config.ini.example to config.ini if 
config.ini does not already exist, and open config.ini in a text editor
(running the script once will also create a blank config.ini file):

```
[Configuration]
mashapekey = keygoeshere
authsession = authsessiongoeshere
```

Replace authsessiongoeshere with your Auth.Session value.

#!/usr/bin/env python

from lxml import html
from pathlib import Path
import argparse
import configparser
import json
import math
import requests
import re
import sqlite3
import sys

# Constants
DECKS_PER_PAGE = 25.0


class Deck:

    """
    An object representing a single Hearthstone deck pulled from HearthPwn.
    """

    def __init__(self, deckid, hero, decktype, rating,
                 dust, updated, decklist):
        # returns (links, classes, types, ratings, dusts, epochs)
        """
        Initialize a HearthPwn Deck object.

        Parameters:

        - 'deckid'   - the HearthPwn ID number of the deck (as seen in the URL)
        - 'hero'     - the Hearthstone class of the deck
        - 'type'     - the deck type (midrange, tempo, control, etc)
        - 'rating'   - the HearthPwn deck rating
        - 'dust'     - dust required to craft deck
        - 'updated'  - epoch timestamp of last update
        - 'decklist' - a list of Card objects
        """

        self.deckid = int(deckid)
        self.hero = str(hero)
        self.type = str(decktype)
        self.rating = int(rating)
        self.dust = int(dust)
        self.updated = int(updated)
        if decklist is not None:
            self.decklist = decklist
        else:
            self.decklist = []

    def __repr__(self):
        output = str(self.deckid) + '\n'
        for card in self.decklist:
            output += str(card.amount) + ' ' + card.cardname + '\n'
        return output

    def get_length(self):
        """
        Return the number of cards in the Deck.

        Parameters:

        'self' - the Deck object calling this function
        """
        length = 0
        # Can't just do a count since you can have 1 or 2 of a card
        # in a given deck.
        for card in self.decklist:
            length += card.amount
        return length


class Card:

    """
    An object representing a card in a Hearthstone deck.
    """

    def __init__(self, cardname, amount):
        """
        Initialize a Hearthstone card object.

        Parameters:

        - 'cardname' - the text name of a Hearthstone card
        - 'amount' - the number of this card included in the parent deck
        """
        self.cardname = str(cardname)
        self.amount = int(amount)

    def __repr__(self):
        return str(self.amount) + 'x ' + self.cardname


def main():
    print("Loading Argument Parser")
    argparser = build_argparser()
    args = argparser.parse_args()
    print("Argument Parser Loaded")
    print("Loading Config Parser")
    config = build_configparser()
    print("Config Parser Loaded")
    operselected = (args.builddecks or args.buildcards or
                    args.buildcollection or args.results)
    if not operselected:
        # TODO: Swap to actual Python error/exception handling?
        print('ERROR: You must use --builddecks, --buildcards,'
              ' and/or --buildcollection')
        parser.print_help()
        sys.exit(-1)
    mashape_key = config['Configuration']['MashapeKey']
    auth_session = config['Configuration']['AuthSession']
    print("Connecting to SQLite3")
    conn = sqlite3.connect('hearth.db')
    cursor = conn.cursor()
    print("SQLite3 Connected")

    if args.buildcards:
        print("Building card database...")
        populate_card_db(get_cards(mashape_key), cursor)

    if args.buildcollection:
        print("Building collection database...")
        populate_collection_db(get_collection(auth_session), cursor)

    if args.builddecks:
        print("Building deck database...")
        # TODO: Consolidate this into one function call
        if args.perclass:
            decks = get_decks_per_class(args.filtering, args.sorting,
                                        args.count, args.patch)
        else:
            decks = get_decks(args.filtering, args.sorting,
                              args.count, args.patch)
        populate_deck_db(decks, cursor)

    dbchanged = (args.buildcards or args.builddecks or args.buildcollection)
    if dbchanged:
        print("Committing changes")
        conn.commit()

    if args.results:
        # TODO: More options when displaying results. For now, for anything
        # other than the default has to be queried from the DB directly.
        results = get_db_card_percentages(cursor)
        print("cardname, hero, totaldecks, avgperdeck, "
              "percentdecks, incollection")
        for row in results:
            if row[2] != 0 and row[3] != 0 and row[4] != 0:
                print("{0}, {1}, {2}, {3:0.2f}, {4:0.2f}%, {5}"
                      .format(row[0], row[1], row[2], row[3], row[4], row[5]))

    conn.close()
    print('Complete!')


def build_argparser():
    """
    Builds the argparser object with all of the arguments and help text.
    """
    desc = ("Scrape Hearthstone decks from HearthPwn (http://hearthpwn.com), "
            "then build a SQLite database of the results. Can also scrape "
            "card collection data from HearthPwn/Innkeeper "
            "(http://innkeeper.com), and integrates with omgvamp's Mashape "
            "Hearthstone API (http://hearthstoneapi.com) to build a table of "
            "card data that can be used to make more advanced queries.")
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('--buildcards', action='store_true',
                        help='build card database from Mashape')
    parser.add_argument('--builddecks', action='store_true',
                        help='build deck database from HearthPwn')
    parser.add_argument('--buildcollection', action='store_true',
                        help='build personal card collection from Hearthpwn')
    # TODO: Possibly make this just a value passed in for --builddecks?
    parser.add_argument('--perclass', action='store_true',
                        help='get the same number of decks for each class')
    parser.add_argument('--count', type=int,
                        help='number of decks to retrieve (per class, if'
                             ' --perclass is set)')
    parser.add_argument('--filtering',
                        help='the HearthPwn filter used when finding decks, '
                             'as seen in the HearthPwn URL')
    parser.add_argument('--sorting',
                        help='the HearthPwn sorting used when finding '
                             'decks, as seen in the HearthPwn URL after '
                             '"&sort="')
    parser.add_argument('--patch', type=int,
                        help='the HearthPwn patch ID used when finding '
                             'decks, as seen in the HearthPwn URL after '
                             '"&filter-build="')
    parser.add_argument('--results', action='store_true',
                        help='for all cards, '
                             'display (in a CSV-ish format) the: '
                             'cardname, '
                             'hero (or neutral), '
                             'total count of decks using the card, '
                             'percentage of decks using the card, '
                             'average count of the card in decks using it, '
                             'and the count of the card in your collection.')
    return parser


def build_configparser():
    """
    Builds the configparser object, and creates any missing config,
    saving the config.ini file when done.
    """
    mashape_key = ''
    legacy_mashape_file = Path("./mashape_key.txt")
    if legacy_mashape_file.is_file():
        mashape_key = legacy_mashape_file.read_text().strip()
        print('Found legacy mashape_key.txt file.')
        print('Read key: ' + mashape_key)
        # We have the key from the legacy file. Remove it.
        legacy_mashape_file.unlink()
    config = configparser.ConfigParser()
    config.read('config.ini')

    configupdated = False
    if not config.has_section('Configuration'):
        print('Adding Configuraiton section to config.ini.')
        config.add_section('Configuration')
        configupdated = True
    if not config.has_option('Configuration', 'MashapeKey'):
        print('MashapeKey does not exist in config.ini.')
        if len(mashape_key) > 0:
            print(' Adding value ' + mashape_key + '.')
        else:
            print(' Adding blank entry.')
        config['Configuration']['MashapeKey'] = mashape_key
        configupdated = True
    if not config.has_option('Configuration', 'AuthSession'):
        print('AuthSession does not exist in config.ini.')
        print('Adding blank entry.')
        config['Configuration']['AuthSession'] = ''
        configupdated = True
    if configupdated:
        with open('config.ini', 'w') as configfile:
            config.write(configfile)
    return config


def get_decks_per_class(filtering=None, sorting=None, count=None, patch=None):
    """
    Retrieve Decks from HearthPwn as a list of Deck objects, ensuring the same
    number of decks are retrieved for each class..

    Parameters:

    'filtering' - the HearthPwn filter used when finding decks, as seen in the
    HearthPwn URL
    'sorting' - the HearthPwn sorting used when finding decks, as seen in the
    HearthPwn URL after "&sort="
    'count' - number of decks to retrieve
    'patch' - the HearthPwn patch ID used when finding decks, as seen in the
    HearthPwn URL after "&filter-build="
    """
    # HearthPwn assigns each class a "power of two" value for filtering by
    # class so that you can AND the values and filter by multiple classes.
    # Since we want to query each class individually (to get the same number
    # of results for each class), calculating powers of 2 works fine.
    classes = [2**x for x in range(2, 11)]
    decks = []

    if not count:
        # Substitute a default count in here so that all classes return the
        # same number of decks. The default count is 10% of the total decks
        # for the current filtering/sorting/patch.
        url = generate_url(filtering, sorting, patch)
        pagecount = get_pagecount(get_htmlelement_from_url(url))
        count = int((pagecount * DECKS_PER_PAGE * 0.1) / len(classes))
    for classid in classes:
        decks += get_decks(filtering, sorting, count, patch, classid)
    return decks


def get_decks(filtering=None, sorting=None, count=None,
              patch=None, classid=None):
    """
    Retrieve Decks from HearthPwn as a list of Deck objects.

    Parameters:

    'filtering' - the HearthPwn filter used when finding decks, as seen in the
    HearthPwn URL
    'sorting' - the HearthPwn sorting used when finding decks, as seen in the
    HearthPwn URL after "&sort="
    'count' - number of decks to retrieve
    'patch' - the HearthPwn patch ID used when finding decks, as seen in the
    HearthPwn URL after "&filter-build="
    'classid' - the HearthPwn class ID used when finding decks, as seen in the
    HearthPwn URL after "&filter-class="
    """
    decks_metainfo = get_deck_metainfo(filtering, sorting, count,
                                       patch, classid)

    decks = []
    total = len(decks_metainfo)
    for counter, deck in enumerate(decks_metainfo):
        print("Adding deck " + str(counter+1) + " of " + str(total))
        decks += [Deck(deck[0], deck[1], deck[2], deck[3], deck[4], deck[5],
                  get_deck_list(deck[0]))]

    return decks


def get_deck_list(deckid):
    """
    For a given HearthPwn deck ID, return a list of Cards that belong to that
    deck.

    Parameters:

    'deckid' - a HearthPwn deck ID
    """
    # http://www.hearthpwn.com/decks/listing/ + deckid + /neutral or /class
    url = 'http://www.hearthpwn.com/decks/listing/'
    css = '#cards > tbody > tr > td.col-name'

    deck = []

    # Class Cards
    htmlelement = get_htmlelement_from_url(url + str(deckid) + '/class')
    cardelements = htmlelement.cssselect(css)
    # Neutral Cards
    htmlelement = get_htmlelement_from_url(url + str(deckid) + '/neutral')
    cardelements += htmlelement.cssselect(css)

    regex = re.compile('&#215;\s+(\d+)')
    for element in cardelements:
        # cssselect always returns an array, but in our case the result is
        # always just one element.
        cardname = element.cssselect('a')[0].text.strip()
        elementtext = html.tostring(element).decode('UTF-8')
        # There's probably a better way to get the amount, but we currently
        # look for the "x #" in the raw text of the element
        match = re.search(regex, elementtext)
        if match:
            amount = int(match.group(1))
        else:
            print('ERROR: Unable to get amount for card ' + cardname)
            # This shouldn't happen, but when it does, just continue on after
            # logging an error.
            amount = 0
        deck.append(Card(cardname, amount))

    return deck


def get_htmlelement_from_url(url):
    """
    Using requests and LXML's HTML module, retrieve a URL and return the page
    as an LXML HtmlElement.

    Parameters:

    'url' - the URL of the webpage to get
    """
    response = requests.get(url)
    htmlelement = html.fromstring(response.text)
    return htmlelement


def get_attributes_from_page(htmlelement, css, attribute):
    """
    Using LXML, get all of the attributes from a HtmlElement that match a css
    selector, and then return a list containing the contents of a given
    attribute for each element.

    Parameters:

    'htmlelement' - the HtmlElement containing elements to select from
    'css' - string containing the CSS selector
    'attribute' - string containing the attribute
    """
    elements = htmlelement.cssselect(css)
    attributes = [element.attrib[attribute] for element in elements]
    return attributes


def get_latest_patch():
    """
    Get the latest patch ID from HearthPwn
    """
    htmlelement = get_htmlelement_from_url('http://www.hearthpwn.com/decks')
    css = '#filter-build > option'
    patches = get_attributes_from_page(htmlelement, css, 'value')
    # Filtering out the empty/none result using list comprehension magic.
    patches = [patch for patch in patches if patch]
    patches.sort(key=int, reverse=True)
    return patches[0]


def get_pagecount(htmlelement):
    """
    Gets the total number of pages on a HearthPwn search from a htmlelement.
    """
    css = ('#content > section > div > div > div.listing-header >'
           'div.b-pagination.b-pagination-a > ul > li:nth-child(7) > a')
    pagecount = htmlelement.cssselect(css)[0].text
    print('Pagecount: ' + pagecount)
    return int(pagecount)


def generate_url(filtering=None, sorting=None, patch=None, classid=None):
    """
    Combines all factors used for sorting into a url.

    Default values are also substitued in here.

    Parameters:

    'filtering' - the HearthPwn filter used when finding decks, as seen in the
    HearthPwn URL
    'sorting' - the HearthPwn sorting used when finding decks, as seen in the
    HearthPwn URL after "&sort="
    'patch' - the HearthPwn patch ID used when finding decks, as seen in the
    HearthPwn URL after "&filter-build="
    'classid' - the HearthPwn class ID used when finding decks, as seen in the
    HearthPwn URL after "&filter-class="
    """
    # TODO: Rework this -- doesn't make sense to have default values but also
    # take into account the posibility of no value being present.
    if not filtering:
        # TODO: Complete documenting this default filtering
        # &filter-unreleased-cards=f - remove any unreleased cards
        # &filter-quality-free-max=29 - remove any decks with 30/all free cards
        filtering = ('filter-is-forge=2&filter-unreleased-cards=f'
                     '&filter-deck-tag=1&filter-deck-type-val=8'
                     '&filter-deck-type-op=4'
                     '&filter-quality-free-max=29')

    if not sorting:
        # Defaulting to sorting by decks with the most views
        sorting = '-viewcount'

    if not patch:
        patch = get_latest_patch()

    # To make things a bit easier on us, sorting, patch, and classid are all
    # compiled into the filtering.

    # Combine patch and filtering
    if patch and filtering:
        # This is separate from the filter attribute to make it easier to only
        # pull decks from the most recent patch.
        if filtering[-1] != '?' and filtering[-1] != '&':
            filtering += '&'
        filtering += 'filter-build=' + str(patch)
    elif patch:
        # Not currently used as filtering has a default above, but leaving just
        # in case I change how this works in the future.
        filtering = 'filter-build=' + str(patch)

    # Combine classid and filtering
    if classid and filtering:
        # This is separate from the filter attribute to make it easier to only
        # pull decks from a single class. This means we can, for example, get
        # the top 1000 decks from each class.
        if filtering[-1] != '?' and filtering[-1] != '&':
            filtering += '&'
        filtering += 'filter-class=' + str(classid)
    elif classid:
        filtering = 'filter-class=' + str(classid)

    # Combine sorting and filtering
    if sorting and filtering:
        if filtering[-1] != '?' and filtering[-1] != '&':
                filtering += '&'
        filtering += 'sort=' + sorting
    elif sorting:
        filtering = 'sort=' + sorting

    if filtering:
        url = 'http://www.hearthpwn.com/decks?' + filtering
    else:
        url = 'http://www.hearthpwn.com/decks'
    return url


def get_deck_metainfo(filtering=None, sorting=None, count=None,
                      patch=None, classid=None):
    """
    Gets a list of (links, classes, types, ratings, dusts, epochs)
    from HearthPwn using the provided paramters.

    Parameters:

    'filtering' - the HearthPwn filter used when finding decks, as seen in the
    HearthPwn URL
    'sorting' - the HearthPwn sorting used when finding decks, as seen in the
    HearthPwn URL after "&sort="
    'count' - number of decks to retrieve
    'patch' - the HearthPwn patch ID used when finding decks, as seen in the
    HearthPwn URL after "&filter-build="
    'classid' - the HearthPwn class ID used when finding decks, as seen in the
    HearthPwn URL after "&filter-class="
    """
    url = generate_url(filtering, sorting, patch, classid)

    if not count:
        # Get a 10% sampling of the pages for the current
        # filtering/sorting/patch/classid
        pagecount = get_pagecount(get_htmlelement_from_url(url))
        count = int(pagecount * .1)

    pagecount = math.ceil(count / DECKS_PER_PAGE)

    regex = re.compile('^\s*\/decks\/(\d+)')
    output = []
    # Adding one as range is exclusive
    for pagenum in range(1, int(pagecount)+1):

        # For each page, get a list of decks from all of the href attributes.
        # Then for each list of decks, pull out the deck ID using regex.
        # Finally, if there is a match, append the deck ID to the deckids list.

        if pagenum == 1:
            htmlelement = get_htmlelement_from_url(url)
        else:
            page = '&page=' + str(pagenum)
            htmlelement = get_htmlelement_from_url(url + page)

        # This CSS selector grabs all of the a (HTML hyperlink) elements in the
        # HearthPwn decks table (being specific to make sure we get the right
        # elements.) We can pull the deck IDs from the HREF attribute.
        css = '#decks > tbody > tr > td.col-name > div > span > a'
        links = htmlelement.cssselect(css)
        css = '#decks > tbody > tr > td.col-deck-type > span'
        decktypes = htmlelement.cssselect(css)
        css = '#decks > tbody > tr > td.col-class'
        heros = htmlelement.cssselect(css)
        css = '#decks > tbody > tr > td.col-ratings > div'
        ratings = htmlelement.cssselect(css)
        css = '#decks > tbody > tr > td.col-dust-cost'
        dusts = htmlelement.cssselect(css)
        css = '#decks > tbody > tr > td.col-updated > abbr'
        epochs = htmlelement.cssselect(css)

        links = [link.attrib['href'] for link in links]
        types = [decktype.text for decktype in decktypes]
        classes = [hero.text for hero in heros]
        ratings = [rating.text for rating in ratings]
        dusts = [dust.text.replace(",", "").replace("k", "00").replace(".", "")
                 for dust in dusts]
        epochs = [epoch.attrib['data-epoch'] for epoch in epochs]

        for x in range(len(links)):
            match = re.search(regex, links[x])
            links[x] = int(match.group(1))

        output += list(zip(links, classes, types, ratings, dusts, epochs))

    return output[:count]


def populate_deck_db(decks, cursor):
    """
    (Re)populates deck information in the SQLite database.

    Parameters:

    'decks' - a list of Deck objects
    'cursor' - a SQLite3 cursor object
    """
    cursor.execute('DROP TABLE IF EXISTS decks')
    cursor.execute('DROP TABLE IF EXISTS deck_lists')
    cursor.execute('''CREATE TABLE IF NOT EXISTS decks
             (deckid integer primary key, class text, type text,
             rating integer, dust integer, updated integer)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS deck_lists
             (deckid integer, cardname text, amount integer,
              PRIMARY KEY (deckid, cardname))''')
    for deck in decks:
        cursor.execute('''INSERT INTO decks (class, type, rating, dust, updated)
                        VALUES ( ?, ?, ?, ?, ?)''',
                       (deck.hero, deck.type, deck.rating,
                        deck.dust, deck.updated))
        last_id = cursor.lastrowid
        for card in deck.decklist:
            cursor.execute('INSERT INTO deck_lists VALUES (?, ?, ?)',
                           (last_id, card.cardname, card.amount))
    return


def get_cards(mashape_key):
    """
    Gets a list of all current Hearthstone cards from omgvamp's mashape
    Hearthstone API, and returns them as a json object.
    """
    if len(mashape_key) <= 0:
        print('Mashape API key does not exist in config.ini')
        sys.exit(-1)
    url = "https://omgvamp-hearthstone-v1.p.mashape.com/cards?collectible=1"
    headers = {"X-Mashape-Key": mashape_key}
    response = requests.get(url, headers=headers)
    try:
        cards = json.loads(response.text)
    except json.decoder.JSONDecodeError:
        print("Unable to decode (possibly empty) response.")
        print("Response: " + response.text)
        sys.exit(-1)
    return cards


def populate_card_db(cards, cursor):
    """
    Populates card information in the SQLite database.

    Parameters:

    'cards' - a JSON object containing a card collection, obtained from the
              Mashape API
    'cursor' - a SQLite3 cursor object
    """
    cursor.execute('DROP TABLE IF EXISTS cards')
    cursor.execute('''CREATE TABLE IF NOT EXISTS cards
                      (cardname text, cardset text,
                       hero text, rarity text,
                       PRIMARY KEY (cardname))''')
    # Removing invalid sets from our results. For the most part, these sets are
    # empty lists as we filter out non-collectible cards. The Mashape API
    # includles cardsets without collectible cards, such as 'System',
    # 'Credits', and 'Debug'. We also explicitly remove the 'Hero Skins' set as
    # they are considered "collectible cards" by HearthStone, but not for our
    # purposes. We will filter out cards where "type": "Hero" later for
    # similar reasons.
    valid_cardsets = {cardset: cards for cardset, cards in cards.items()
                      if cards and cardset != 'Hero Skins'}
    for cardset in valid_cardsets:
        for card in cards[cardset]:
            if card['type'] != 'Hero':
                cursor.execute('INSERT INTO cards VALUES (?, ?, ?, ?)',
                               (card['name'], card['cardSet'],
                                card.get('playerClass', 'Neutral'),
                                card['rarity']))
    return


def get_collection(auth_session):
    """
    Gets a list of all cards in your HearthPwn collection,
    and returns them as a json object.
    """
    if len(auth_session) <= 0:
        print('Auth Session does not exist in config.ini')
        sys.exit(-1)
    url = "http://www.hearthpwn.com/ajax/collection"
    cookies = dict({'Auth.Session': auth_session})
    response = requests.get(url, cookies=cookies)
    try:
        collection = json.loads(response.text)
    except json.decoder.JSONDecodeError:
        print("Unable to decode (possibly empty) response.")
        print("Response: " + response.text)
        sys.exit(-1)
    return collection


def populate_collection_db(collection, cursor):
    """
    Populates collection information in the SQLite database.

    Parameters:

    'collection' - a JSON object containing a card collection, obtained from
                   http://www.hearthpwn.com/ajax/collection
    'cursor' - a SQLite3 cursor object
    """
    # TODO: Possibly skip all of this if the collection hasn't been updated
    # since the last time this was ran.
    # The collection JSON contains the last update time:
    # Ex: { "updatedDate":"4/20/2017 2:39:54 PM"
    cursor.execute('DROP TABLE IF EXISTS collection')
    cursor.execute('''CREATE TABLE IF NOT EXISTS collection
                      (cardname text, amount integer,
                       PRIMARY KEY (cardname))''')

    total = len(collection['cards'])
    for counter, card in enumerate(collection['cards']):
        print("Adding card " + str(counter+1) + " of " + str(total) +
              " to collection.")
        cardname = get_cardname(card['externalID'], cursor)
        # HearthPwn can return 3/4 if you have normal + gold copies of a card.
        # We just care how many "usable" copies you have, regardless of rarity.
        amount = min(card['count'], 2)
        cursor.execute('INSERT INTO collection VALUES (?, ?)',
                       (cardname, amount))
    return


def get_cardname(card_id, cursor):
    """
    Given a HearthPwn card ID, retrieve the cardname for that ID.
    First attempts to find the cardname in the local database,
    and if it's not found, looks up the ID on HearthPwn and stores
    that name in the local DB.

    Parameters:

    'card_id' - the integer ID of the card to find the name of
    'cursor' - a SQLite3 cursor object
    """
    url = "http://www.hearthpwn.com/cards/" + str(card_id)
    css = "#content > section > div > header.h2.no-sub.with-nav > h2"

    cursor.execute('''CREATE TABLE IF NOT EXISTS card_ids
                      (cardname text, cardid integer,
                       PRIMARY KEY (cardid))''')

    cursor.execute('SELECT cardname FROM card_ids WHERE cardid IS ?',
                   (card_id,))
    cardname = cursor.fetchone()

    if cardname:
        # We can't do this before without try/catch -- if there are no results,
        # the query returns none, and trying to get the [0]th element of None
        # results in a TypeError.
        cardname = cardname[0]
    else:
        print('Cardname for HearthPwn card ID ' + str(card_id) +
              ' not found in local DB.')
        # Card ID <-> Card Name mapping wasn't found in the local DB
        htmlelement = get_htmlelement_from_url(url)
        # cssselect always returns an array, but in our case the result
        # should just be one element.
        cardname = htmlelement.cssselect(css)[0].text.strip()
        cursor.execute('INSERT INTO card_ids VALUES (?, ?)',
                       (cardname, card_id))
    return cardname


def get_db_deck_updated(cursor, deckid):
    """
    Returns the timestamp of the specified deck

    Parameters:

    'cursor' - a SQLite3 cursor object
    'deckid' - a HearthPwn deck ID
    """
    cursor.execute('SELECT updated FROM decks WHERE deckid IS ?', (deckid,))
    return cursor.fetchone()[0]


def get_db_card_percentages(cursor):
    """
    For all cards, return: (cardname, total decks using the card, percentage
    of decks using the card, and average number of the card in a deck) from
    the database.

    Parameters:

    'cursor' - a SQLite3 cursor object
    """
    sql = '''
            select cards.cardname,
                    cards.hero,
                    case
                        when deck_lists.cardname is null then 0
                        else count(*)
                    end as [total],
                    avg(coalesce(deck_lists.amount, 0)) as [per deck],
                    case
                        when deck_lists.cardname is null then 0.0
                        else count(*) /
                        (select cast(count(*) as double) from decks) * 100.0
                    end as [percent],
                    coalesce(collection.amount, 0) as collected
            from cards
            left join deck_lists
            on cards.cardname = deck_lists.cardname
            left join collection
            on cards.cardname = collection.cardname
            where cards.cardset in ('Classic',
                                    'Whispers of the Old Gods',
                                    'Mean Streets of Gadgetzan',
                                    'Journey to Un''Goro')
            group by cards.cardname
            order by Total desc
            '''
    results = cursor.execute(sql)
    return results

if __name__ == "__main__":
    # Execute only if run as a script
    main()

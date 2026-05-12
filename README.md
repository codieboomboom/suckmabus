# Overview
This is a telegram bot written with telegram bot API to help with checking of bus timing

# Requirements
## Register new bus stop
This feature allow a user to register a new bus stop to their "saved" bus stop. The following step/flow should be taken:

- [DONE] User invoke this command `/reg` on the Telegram's chat with the bot
- [DONE] The bot recognize that the user wanted to register a new bus stop and ask the user to key in a bus stop number (move to PEND_BUS_STOP stage)
- [DONE] The user send as message of bus stop number inside the chat thread with Telegram bot
- [DONE] The bot validates if:
    + [OK] Message contains a bus stop number (containing all digits)
    + [OK] Whether the bus stop exist/valid by cross-checking with the database
    + [OK] Whether this bus stop have already been saved before.
- [DONE] The bot get information about bus stop (name, road, etc) via the database AND save the bus stop number in a temporary storage
- [DONE] The bot confirm with user if the bus stop they supply is correct (inline keyboard)
    + No, cancel the register intention and go back to IDLE state
    + Yes, move from PEND_BUS_STOP to PEND_ALIAS state
- [NOT SUPPORTED] The bot ask user for alias and save that plus bus stop number (stored in temp) into db. Go back to IDLE state

## Deregister bus stops
This feature allow a user to deregister 1 bus stop from their "saved" list
- [DONE] The user invoke `/dereg` command
- [DONE] The bot query database for whatever bus stop information that is saved
- [DONE] The bot present an inline keyboard/menu that shows all bus stop as blocks and prompt user to select 1 to deregister (show by bus stop number and by alias, fallback is bus stop number) | IF EMPTY THEN TELL USER NOTHING TO DEREGISTER
- [DONE] User click on the bus stop they wish to deregister and the bot take that away from the database. End of feature

## Modify bus stops (NOT SUPPORTED until alias is supported)
This feature allow a user to modify 1 bus stop entry under their saved list
- The user invoke `/modify` command
- The bot query the database for "saved" bus stops and information
- The bot present all bus stop in inline keyboard/menu and let the user choose which one to modify
- The bot ask user to key/msg a new alias
- The user type the alias and send as message
- The bot receive and update the entry in db

## Check bus stops arriving bus
This feature allow a user to check for arriving bus for 1 bus stop that is on their saved list
- [DONE] The user invoke `/check` command
- [DONE] The bot query the database for "saved" bus stops and information
- [DONE] The bot present all bus stop in inline keyboard/menu and wait for user to choose
- [DONE] User choose and click on the inline option that they interested
- [DONE: query locally] The bot query LTA databases for the arrival time of all buses at that bus stop
- [DONE] The bot send as a message the update of arrival time to user.

# Future checklist
- Multi-user [OK]
- Fresheness timestamp for bus stop?

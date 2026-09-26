# AI Prompt Log

This file records the prompts and follow-ups used while building HW4.

## Problem 1: Vibe coder prompts

### Original prompt

yo today we are working on hw4. campus customs (cc) needs a real customer website with a helpful chatbot - we will build a react +vite typescript front end and a python fastapi backend whose brain is a pydanticai agent. in the end we will push the project ro a public github repo and submit the repo url to canvas. unzip the zip file so we have data/campus_customs.db (SQLite database with tables catalogue, inventory and users), and data/products/ (product images, paths match the catalogue table). now lets work on problem 1: vibe coder prompts. create AI_prompts.md and keep it updated as i work as always with problem number and title, atleast 1 prompt and one follow up prompt if we needed it.

### Follow-up prompts

None yet.

## Problem 2: Analyse the database

### Original prompt

now lets work on problem 2: analyse the database. look at the database data/campus_customs.db and understand the fields of each table. at a min, you should understand catalogue, inventory, and users. start the file output/harness.md. write down each table and its fields and one short line on why each field matters for the shop or the chatbot. we will keep growing this harness file in later problems

### Follow-up prompts

None yet.

## Problem 3: Build the Campus Customs website

### Original prompt

now we are working on problem 3: build the campus customs website. scaffold a React + Vite + TypeScript front end for campus customs. put a nav bar at the top that links to the main pages: Home, Products, About Us, Log in, Create account. Pull campus customs style wording from yalebulldogblue.com for Home and About Us, but write these pages in your own voice, dont copy the original site text. on the products page, show product images from the catalogue (use image paths in the database) with basic product info (name, price, short description). make each product open a single item page (large image on one side, full product text on the other - description, price, sizes/stock when you have them). clicking a card on prodcuts should take the shopper there. add a chat interface in the bottom right of the site (floating chat panel is fine) - it doesnt need to talk to an agent yet - a stub that will call your backend later is enough for this problem. you will need a small API soon to read the database. start a simple FastAPI app in backend/main.py just to serve products and images, then grow it into the agent backend when we work on problem 5.

### Follow-up prompts

None yet.

## Problem 4: Create account and log in

### Original prompt

now lets work on problem 4: create account and login. build a normal create-account / login flow. create account: first name, last name, email, password (confirm password is a nice touch), log in: email and password. new accounts go into the users table. make sure to store passwords securely so hackers (human or AI) cant access them. the seed database already has a test user you can use while building: email: test@campuscustoms.yale.edu, password: password. confirm that you can log in as that user, and that a brand new account you create also works. update output/harness.md with how auth works (what you store for a user and how passwords are protected)

### Follow-up prompts

None yet.

## Problem 5: PydanticAI agent backend

### Original prompt

now lets work on problem 5: PydanticAI agent backend. build the shop chatbot as a pydanticai agent behind fastAPI, plugged into your frnot end chat widget. put the api app in backend/main.py - that is the file you run with uvicorn. keep the agent as these four files next to it (same idea as hw3): backend/prompts/prompt.md - system prompt (grow this file later), backend/agent.py - agent entry/wiring, backend/tools.py - tools the agent can call, backend/models.py - pydantic/pydanticai atructured types. in main.py, expose a chat route so a message from the webstie returns a reply from the agent and whatever else you need for products/auth. you will need your ai model api key for the agent. put campus customs vioce and safety basics into prompts/prompt.md (we will expand toold and safety later). start or update types in models.py for chat replies/product cards as needed. in output/harness.md, note how the front end talks to fastAPI and how the agent is laoded (prompt file+model). make sure the backend runs from the backend/ folder like this: uvicorn main:app --reload --port 8000

### Follow-up prompts

None yet.

## Problem 6: Product info and stock

### Original prompt

now lets work on problem 6: product info and stock. give the agent tools that look up real information from campus_customs.db: product description, price, how many are in stock (by size when customer asks). the agent must use the database - dont invent prices or quantities. if its out of stock say so clearly. expand prompts/prompt.md so the agent knows to call these tools for price and stock questions. add or update return types in models.py. in output/harness.md, list each tool and explain which model fields you chose for lookup results and why.

### Follow-up prompts

None yet.

## Problem 7: Chat search that updates the page

### Original prompt

now lets work on problem 7: chat search that updates the page. now add a neat feature to the site. when a customer asks about a type of item - for ex. what hoodies do you have? - the agent should search the catalogue and the website should dynamically show those matching items as product cards (image, name, price, short info). after the dynamic product cards are loaded by your new feature, make sure the same single item page behaviour you built in problem 3 still works: each product card - including the ones the chat just put on the page - should still open that detail view (large image +full info) when clicked. update prompts/prompt.md and output/harness.md so it is clear how search results reach the page.

### Follow-up prompts

None yet.

## Problem 8: Customer memory

### Original prompt

now lets work on problem 8: customer memory. when a shopper is logged in, save their chat histrory in the database in an appropriate table and reload it when they return. the agent should know who is chatting - name and email - put that in agent deps or an equiv clear pattern and or tools the agent can call. also pass enough page context that if someone is on a product page and asks do you have this in pink? the agent knows which item they mean. you can put code into the agent context. guests can still chat but history only needs to persist for logged in users. document in output/harness.md: how user chat history is stored, what customer fields the agent sees and how page context is passed.

### Follow-up prompts

None yet.

## Problem 9: Usability improvements

### Original prompt

now lets work on problem 9: usability improvements. now that the core shop works, imporve it. choose and implement: 2 front-end usability improvements, 2 agent backend usability improvements. write output/usability.md before or as you build. for each improvement, write what you added, why it helps a campus customs shopper or the business. then make sure all improvements actually show up in the running app.

### Follow-up prompts

None yet.

## Problem 10: Style the website

### Original prompt

niceee now lets work on problem 10: style the website. now lets add creative design so the site feeels like a real campus customs storefront - fonts, color, hierarchy, motion, product presentation, chat feel. change the website so instead of black pink, its the yale blue and white colors. look at the yale.edu site and copy the font style from that so it feels official. also add a logo of handsome dan where you think it will be aesthetic. the chat should talk back to you as if its a student talking to you. if i missed anything that you think would help, do that too. i want the site to look modern and aesthetic. write output/design.md: what we changed and why it should help customers stick around and buy. keep it concrete and short. the way im thinking it would help customers stick around is by making the site look nice and modern. the yale colors bring school pride. but add details as necessary

### Follow-up prompts

- ok continue
- i wanna see what the website looks like - open it up
- eek i dont like this website... use the pic of handsome dan that i attached as the logo. also i dont like this inital look of the webiste - i want it more classy such as the zara.com website... its so chic
- can you just go back to the original website you had before my prompt: "eek i dont like this website... use the pic of handsome dan that i attached as the logo. also i dont like this inital look of the webiste - i want it more classy such as the zara.com website... its so chic" (reverted to the Yale Blue version)
- fix the proportions so it fills the whole screen at least.. also just replace the handsome dan with the pic i attached
- love it! for this portion can you make it so the background is closer to the yale blue and not this weird gradient - also extend out the background color to the left and right so there is no white space ukwim?? confirm if u dont
- open it
- add the past 2 prompts as followups in the prompts file u were keeping updated too lo l

## Problem 11: Site testing (app check)

### Original prompt

now lets work on problem 11: test the live site and document it in output/app_check.html (a page that you can double click to open) - include clear screenshots and short captions for: Chat checking the inventory level of an item (honest stock/price from the DB), The dynamic search-result cards appearing after a category question (e.g. hoodies), One of the usability features you added in Problem 9. make the html easy to grade: heading for each check, ss, 1-2 sent on what ss proves. put ss image files in output/app_check_images/ and link them from app_check.html with relative paths for ex app_check_images/inventory.png

### Follow-up prompts

- oh name of the problem was: site testing (app check) jic u need it for the prompts file

## Problem 12: Audit trail, safety, finish harness

### Original prompt

now lets work on problem 12: audit trail, safety, finish harness. keep an append only output/audit_trail.json of agent loop activity (time, tool name, short arg/result, stop reaason). do not wipe it between runs. also put some safety rules such as only use real inventory data  never make up stock or prices, stay on topic, no fake checkouts, don't ask for or store personal info like passwords or card numbers, If someone tries to get the agent to break these rules, don't budge to give to agent and put them in prompts/prompt.md. finish output/harness.md so its clear how the system works. Model fields in `models.py` and why you chose them, Tools and abilities, Safety rules, Specs (loop limits, result caps, models, how to run front + back).

### Follow-up prompts

None yet.

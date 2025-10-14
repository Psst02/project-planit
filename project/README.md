# PlanIt!
#### Video Demo: https://youtu.be/AHwi7SMMOMw
#### Description:

**PlanIt!** is a lightweight web application designed to simplify group scheduling through shareable invite links.

The workflow is simple: the creator defines event details (focus, setting, participant limits, date range, activity categories). Once submitted, the system generates a unique invite link. Invitees can then access the link to respond by selecting preferred dates, suggesting activities, or declining the invitation. The link expires automatically after a week, ensuring the plan won't be procrastinated. Once responses meet the minimum attendance requirement, the system automatically determines the final date and activities. **PlanIt!** is particularly suitable for small groups, social gatherings, or casual event planning, focusing on simplicity and immediacy, valuable in spontaneous social planning.

#### Acknowledgements:

This project was completed as part of Harvard’s [CS50x](https://pll.harvard.edu/course/cs50-introduction-computer-science) course. Duck mascot is made using [Canva](https://www.canva.com/) and is a tribute to the CS50's duck debugger. Code and solutions were adapted from multiple sources including:
- [Stack Overflow](https://stackoverflow.com/)
- [GeeksforGeeks](https://www.geeksforgeeks.org/)
- [Reddit](https://www.reddit.com/)

Additional guidance came from YouTube tutorials, documentation examples, and AI-assisted tools, specifically [ChatGPT](https://chat.openai.com/), which helped clarify unfamiliar syntax, troubleshoot errors, and optimize code efficiency. Web elements, such as icons and the logo, were sourced from [Bootstrap Icons](https://icons.getbootstrap.com/) and [Favicon.io](https://favicon.io/emoji-favicons/).

#### Implementation Details:

- Language & Framework: Python, Flask
- Database: sqlite3 (`planit.db`)
- Authentication: Google OAuth (Authlib)
- Password Security: Argon2
- Front-end: Jinja templates with Bootstrap
- Session Management: Flask-Session

JavaScript is employed to enhance user interaction and front-end responsiveness, including form validation and dynamic updates of the user interface. **PlanIt!** is hosted on PythonAnywhere, a stable and accessible deployment environment simple enough for beginners. [Click me](https://shin02.pythonanywhere.com/) to visit **PlanIt!**

#### Design Decisions:

Bootstrap utilities were used extensively to minimize custom CSS, keeping the interface consistent and maintainable. The Flask framework was chosen for its simplicity and familiarity from the CS50 problem sets, providing a clear structure for routing, sessions, and templates. Argon2 (argon2-cffi) was selected over Flask’s default Werkzeug hashing for stronger password security while Werkzeug supports essential Flask utilities for secure and efficient request handling.

One major design shift was replacing the friend system with link-based sharing, making the app lighter and more casual. A friend system felt unnecessarily complex for a small-scale planner. Another notable change involved response viewing. Instead of downloadable summaries (.pdf), participants can view responses instantly through the interface, which is more convenient. There was also a dilemma about including a poll voting feature for deciding activities. Although allowing creators to toggle between automated decisions and polls seemed appealing, potential conflicts in results made the process more complicated. To maintain simplicity and efficiency, the feature was ultimately removed.

The project began with CS50 finance problem set files: all logic was managed in `app.py` and `helpers.py` while data was stored in the CS50 SQL library. In the later stages of the development, the database was adapted to sqlite3 to remove hosting dependencies. Then, the functions inside `app.py` were reorganized into blueprints: `acc.py`, `auth.py`, `event.py`, improving clarity and maintainability. At this point, Google OAuth integration was added as a stretch goal using Authlib for the Google OAuth 2.0, aligned with OpenID Connect (OIDC). File paths were also made dynamic to prevent environment-specific errors caused by hardcoding.

#### Project Structure:
```
  app.py        → Flask app configuration & blueprint registration
  helpers.py    → shared utility functions
  auth.py       → authentication routes & logic (blueprint)
  acc.py        → account management routes & logic (blueprint)
  event.py      → event creation, response, and scheduling logic (blueprint)
  templates/    → HTML templates
  static/       → CSS, images
  planit.db     → SQLite database
```

#### Function Overview:

- **auth.py** (User Authentication)
```
  login_google(), google_callback()        → handle Google login
  signup(), login(), logout()              → manage account access
  link_google(), google_link_callback()    → link Gmail accounts
```

- **acc.py** (Account Management)
```
  account_details()    → edit profile, username, link Gmail
  reset_password()     → change/set password
  delete_account()     → permanently delete account
```

- **event.py** (Event Logic)
```
  dashboard()          → shows user-related events
  create_event()       → configure event & generate invite link
  respond_event()      → submit invite response
  show_response()      → view submitted responses
  schedule_event()     → display finalized event details
```

- **helpers.py** (Utility Functions)
```
  login_required()                                       → protect routes
  show_error()                                           → render custom error pages
  unique_username()                                      → add numbers behind duplicate usernames
  remove_photo()                                         → delete profile images
  get_db(), close_db(), db_teardown()                    → manage database connection
  schedule_plan()                                        → determine final event date
  choose_activities()                                    → pick activity suggestions
  evaluate_event()                                       → database lookup before event checks
  common_check(), responses_check(), removal_check()     → event confirmation and cleanup
```

#### Templates:

- Base layouts:
  - `layout.html`
  - `side_bar.html`

- User authentication:
  - `signup.html`
  - `login.html`

- Event overview:
  - `dashboard.html`

- Event creation:
  - `create_event.html`

- Invite responses
  - `rsvp_form.html`
  - `thank_you.html`

- Finalized event details
  - `scheduled.html`

- Error display
  - `error.html`

- Account management
  - `account_details.html`
  - `reset_psw.html`
  - `delete_account.html`

#### About the Developer:

Phyu Sin Shin Thant is a post-graduate in Singapore, aiming to become a full-stack developer and eventually work in cybersecurity. This project is dedicated to her awesome friends who give their all to coordinate plans despite busy schedules.

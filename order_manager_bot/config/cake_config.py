# config/cake_config.py

# --- CAKE CONFIGURATION AND RULES ---
# Defines valid flavors and layer/size constraints.
CAKE_CONFIG = {
    "vanilla bean": {}, "carrot": {}, "lemon": {}, "coconut": {},
    "marble": {}, "chocolate": {}, "strawberry": {}, "cookies and cream": {},
    "red velvet": {}, "banana bread": {}, "caribbean fruit/ rum": {}, 
    "butter pecan": {}, "white chocolate sponge": {}, "pineapple sponge": {},
}

# Defines which sizes are available for a given number of layers.
# Sizes are now simplified to just the inch number or the sheet type.
LAYER_SIZE_CONSTRAINTS = {
    1: ['6', '8', '9', '10', '12', 'quarter sheet', 'half sheet'],
    2: ['6', '8', '9', '10', '12', 'quarter sheet', 'half sheet'],
    3: ['6', '8'],
}
VALID_LAYERS = list(LAYER_SIZE_CONSTRAINTS.keys())

# Lists derived from config for simpler validation checks
VALID_FLAVORS = list(CAKE_CONFIG.keys()) 
VALID_YES_NO = ['yes', 'y', 'no', 'n']

# --- FLOW AND STATE MAPS ---

FLOW_MAP = {
    'START': {
        'question': 'Welcome to the Precious Place Custom Cake Order Bot! I can help you place a custom cake order. We will walk through the required details step-by-step.\n\nType **Restart** at any time to begin the conversation over.\n',
        'data_key': None,
        'next': 'MAIN_MENU', # <<< CHANGED: Go to the main menu first
    },
    'MAIN_MENU': { # <<< NEW STATE: Main choice point
        'question': 'How can I help you today?\n\n*1.* Create a new custom cake order.\n*2.* View your upcoming orders.',
        'data_key': None,
        'next': None, # Handled by custom logic in conversation_handler
    },
    'VIEW_ORDERS': { # <<< NEW STATE: For displaying future orders
        'question': 'Here are your upcoming orders:',
        'data_key': None,
        'next': 'MAIN_MENU', # After viewing, return to the main menu
    },
    'ASK_DATE': {
        'question': 'Let\'s start by telling me the date of the event (Please reply with DD/MM/YYYY)',
        'data_key': 'event_date',
        'next': 'ASK_CUSTOM_PICTURE',
    },
    'ASK_CUSTOM_PICTURE': {
        'question': 'Do you have a picture of the custom cake you would like? (Yes/No)',
        'data_key': 'has_picture',
        'next_if': {
            'yes': 'ASK_IMAGE_UPLOAD',
            'no': 'ASK_FLAVOR',
        },
    },
    'ASK_IMAGE_UPLOAD': {
        'question': 'Great! Please send the picture now. You can also type **Skip** if you change your mind.',
        'data_key': 'image_url',
        'next': 'ASK_FLAVOR',
    },
    'ASK_FLAVOR': {
        'question': f'What flavor would you like? We offer: {", ".join([f.title() for f in VALID_FLAVORS])}.',
        'data_key': 'cake_flavor',
        'next': 'ASK_LAYERS',
    },
    'ASK_LAYERS': {
        'question': f'How many layers would you like? We support: {", ".join(map(str, VALID_LAYERS))} layers.',
        'data_key': 'num_layers',
        'next': 'ASK_SIZE',
    },
    'ASK_SIZE': {
        'question': '', # Dynamic question handled in conversation_handler
        'data_key': 'cake_size',
        'next': 'ASK_TIERS',
    },
    'ASK_TIERS': {
        'question': 'How many tiers (levels) will the cake have? (A number)',
        'data_key': 'num_tiers',
        'next': 'ASK_COLOR',
    },
    'ASK_COLOR': {
        'question': 'What is the primary color of the cake?',
        'data_key': 'cake_color',
        'next': 'ASK_THEME',
    },
    'ASK_THEME': {
        'question': 'What is the theme or general description (e.g., Star Wars, Floral, Simple)?',
        'data_key': 'cake_theme',
        'next': 'ASK_INDOORS',
    },
    'ASK_INDOORS': {
        'question': 'Will the cake be displayed indoors? (Yes/No)',
        'data_key': 'venue_indoors',
        'next': 'ASK_AC',
    },
    'ASK_AC': {
        'question': 'Does the venue have air conditioning? (Critical for stability - Yes/No)',
        'data_key': 'venue_ac',
        'next': 'ASK_CONFIRMATION', 
    },
    'ASK_CONFIRMATION': {
        'question': 'Please review the summary above. Is this information correct and ready to save? (Yes/No)',
        'data_key': None,
        'next_if': {
            'yes': 'SUMMARY',
            'no': 'MAIN_MENU', # <<< CHANGED: Go back to the main menu after confirmation failure
        },
    },
    'SUMMARY': {
        'question': 'Final saving stage.',
        'data_key': None,
        'next': None,
    }
}

# Mapping of technical data keys to human-readable display names for the final summary
DISPLAY_KEY_MAP = {
    'event_date': 'Event Date',
    'cake_flavor': 'Cake Flavor',
    'num_layers': 'Number of Layers',
    'cake_size': 'Cake Size',
    'num_tiers': 'Number of Tiers',
    'cake_color': 'Primary Color',
    'cake_theme': 'Theme/Description',
    'venue_indoors': 'Venue Indoors?',
    'venue_ac': 'Venue with A/C?',
    'has_picture': 'Picture Sent?',
    'image_url': 'Reference Image',
}
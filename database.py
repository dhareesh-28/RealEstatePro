import sqlite3
from flask import g
from datetime import datetime

DATABASE = 'real_estate.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row  # Optional: return dict-like rows
    return db

def init_db(app):
    with app.app_context():
        db = get_db()
        cursor = db.cursor()

        # Users table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            user_type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Properties table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            location TEXT NOT NULL,
            property_type TEXT NOT NULL,
            sq_ft REAL NOT NULL,
            bedrooms INTEGER NOT NULL,
            bathrooms INTEGER NOT NULL,
            year_built INTEGER,
            parking_spaces INTEGER,
            condition TEXT,
            price REAL NOT NULL,
            listing_type TEXT NOT NULL,
            image_path TEXT,
            seller_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (seller_id) REFERENCES users (id)
        )
        ''')

        # Drop existing messages table if it exists
        cursor.execute('DROP TABLE IF EXISTS messages')
        cursor.execute('DROP TABLE IF EXISTS conversations')
        
        # Conversations table to group messages between buyer and seller
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER NOT NULL,
            buyer_id INTEGER NOT NULL,
            seller_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            last_message_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (property_id) REFERENCES properties (id),
            FOREIGN KEY (buyer_id) REFERENCES users (id),
            FOREIGN KEY (seller_id) REFERENCES users (id)
        )
        ''')
        
        # Messages table for individual messages in a conversation
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            is_read BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (conversation_id) REFERENCES conversations (id),
            FOREIGN KEY (sender_id) REFERENCES users (id)
        )
        ''')

        db.commit()

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def insert_user(username, password, email, phone, user_type):
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
    INSERT INTO users (username, password, email, phone, user_type)
    VALUES (?, ?, ?, ?, ?)
    ''', (username, password, email, phone, user_type))
    db.commit()
    return cursor.lastrowid

def insert_property(title, description, location, property_type, sq_ft, bedrooms,
                   bathrooms, year_built, parking_spaces, condition, price,
                   listing_type, image_path, seller_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
    INSERT INTO properties (title, description, location, property_type, sq_ft,
                          bedrooms, bathrooms, year_built, parking_spaces,
                          condition, price, listing_type, image_path, seller_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (title, description, location, property_type, sq_ft, bedrooms,
          bathrooms, year_built, parking_spaces, condition, price,
          listing_type, image_path, seller_id))
    db.commit()
    return cursor.lastrowid

def get_user_by_username(username):
    return query_db('SELECT * FROM users WHERE username = ?', [username], one=True)

def get_properties(listing_type=None, location=None, property_type=None, bedrooms=None, price_range=None):
    query = 'SELECT * FROM properties WHERE 1=1'
    params = []
    
    if listing_type:
        query += ' AND listing_type = ?'
        params.append(listing_type)
    
    if location:
        query += ' AND location = ?'
        params.append(location)
    
    if property_type:
        query += ' AND property_type = ?'
        params.append(property_type)
    
    if bedrooms:
        if bedrooms == '3+':
            query += ' AND bedrooms >= 3'
        else:
            query += ' AND bedrooms = ?'
            params.append(int(bedrooms))
    
    if price_range:
        if listing_type == 'rent':
            if price_range == 'Under ₹20K':
                query += ' AND price < 20000'
            elif price_range == '₹20K - ₹50K':
                query += ' AND price >= 20000 AND price <= 50000'
            elif price_range == '₹50K - ₹1L':
                query += ' AND price > 50000 AND price <= 100000'
            elif price_range == 'Above ₹1L':
                query += ' AND price > 100000'
        else:
            if price_range == 'Under ₹50L':
                query += ' AND price < 5000000'
            elif price_range == '₹50L - ₹1Cr':
                query += ' AND price >= 5000000 AND price <= 10000000'
            elif price_range == '₹1Cr - ₹2Cr':
                query += ' AND price > 10000000 AND price <= 20000000'
            elif price_range == 'Above ₹2Cr':
                query += ' AND price > 20000000'
    
    return query_db(query, params)

def get_property_by_id(property_id):
    return query_db('''
        SELECT p.*, u.username as seller_name, u.email as seller_email, u.phone as seller_phone 
        FROM properties p 
        JOIN users u ON p.seller_id = u.id 
        WHERE p.id = ?
    ''', [property_id], one=True)

def get_user_properties(user_id):
    return query_db('SELECT * FROM properties WHERE seller_id = ?', [user_id])

def get_or_create_conversation(property_id, buyer_id, seller_id):
    db = get_db()
    cursor = db.cursor()
    
    # Check if conversation already exists
    cursor.execute('''
    SELECT id FROM conversations 
    WHERE property_id = ? AND buyer_id = ? AND seller_id = ?
    ''', (property_id, buyer_id, seller_id))
    
    conversation = cursor.fetchone()
    
    if conversation:
        return conversation[0]
    
    # Create new conversation
    cursor.execute('''
    INSERT INTO conversations (property_id, buyer_id, seller_id)
    VALUES (?, ?, ?)
    ''', (property_id, buyer_id, seller_id))
    db.commit()
    return cursor.lastrowid

def insert_message(property_id, sender_id, sender_name, sender_email, sender_phone, message):
    db = get_db()
    cursor = db.cursor()
    
    # Get seller_id from property
    cursor.execute('SELECT seller_id FROM properties WHERE id = ?', [property_id])
    property = cursor.fetchone()
    if not property:
        raise Exception("Property not found")
    
    seller_id = property[0]
    
    # Get or create conversation
    conversation_id = get_or_create_conversation(property_id, sender_id, seller_id)
    
    # Insert message
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
    INSERT INTO messages (conversation_id, sender_id, message, created_at)
    VALUES (?, ?, ?, ?)
    ''', (conversation_id, sender_id, message, current_time))
    
    # Update conversation's last_message_at
    cursor.execute('''
    UPDATE conversations 
    SET last_message_at = ? 
    WHERE id = ?
    ''', (current_time, conversation_id))
    
    db.commit()
    return cursor.lastrowid

def get_conversations_for_user(user_id, user_type):
    if user_type == 'buyer':
        return query_db('''
            SELECT c.*, p.title as property_title, p.location as property_location,
                   u.username as other_party_name,
                   (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id AND m.is_read = 0 AND m.sender_id != ?) as unread_count,
                   (SELECT message FROM messages WHERE conversation_id = c.id ORDER BY created_at DESC LIMIT 1) as last_message,
                   (SELECT created_at FROM messages WHERE conversation_id = c.id ORDER BY created_at DESC LIMIT 1) as last_message_time
            FROM conversations c
            JOIN properties p ON c.property_id = p.id
            JOIN users u ON c.seller_id = u.id
            WHERE c.buyer_id = ?
            ORDER BY c.last_message_at DESC
        ''', [user_id, user_id])
    else:  # seller
        return query_db('''
            SELECT c.*, p.title as property_title, p.location as property_location,
                   u.username as other_party_name,
                   (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id AND m.is_read = 0 AND m.sender_id != ?) as unread_count,
                   (SELECT message FROM messages WHERE conversation_id = c.id ORDER BY created_at DESC LIMIT 1) as last_message,
                   (SELECT created_at FROM messages WHERE conversation_id = c.id ORDER BY created_at DESC LIMIT 1) as last_message_time
            FROM conversations c
            JOIN properties p ON c.property_id = p.id
            JOIN users u ON c.buyer_id = u.id
            WHERE c.seller_id = ?
            ORDER BY c.last_message_at DESC
        ''', [user_id, user_id])

def get_messages_for_conversation(conversation_id):
    return query_db('''
        SELECT m.*, u.username as sender_name, u.user_type as sender_type
        FROM messages m
        JOIN users u ON m.sender_id = u.id
        WHERE m.conversation_id = ?
        ORDER BY m.created_at ASC
    ''', [conversation_id])

def mark_conversation_messages_as_read(conversation_id, user_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
    UPDATE messages 
    SET is_read = 1 
    WHERE conversation_id = ? AND sender_id != ?
    ''', [conversation_id, user_id])
    db.commit()

def get_unread_message_count(user_id, user_type):
    if user_type == 'buyer':
        return query_db('''
            SELECT COUNT(*) as count
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE c.buyer_id = ? AND m.sender_id != ? AND m.is_read = 0
        ''', [user_id, user_id])[0]['count']
    else:  # seller
        return query_db('''
            SELECT COUNT(*) as count
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE c.seller_id = ? AND m.sender_id != ? AND m.is_read = 0
        ''', [user_id, user_id])[0]['count']

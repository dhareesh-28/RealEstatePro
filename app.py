from flask import Flask, render_template, request, redirect, url_for, session, flash, g
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from model import predict_price
from rent_model import predict_rent
import os
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = 'static/images/properties'

# Import database functions
from database import (
    get_db, init_db, insert_user, insert_property, get_user_by_username, 
    get_properties, get_property_by_id, get_user_properties, insert_message, 
    get_conversations_for_user, get_messages_for_conversation, 
    mark_conversation_messages_as_read, get_unread_message_count
)

# Initialize database
with app.app_context():
    init_db(app)
    if not get_properties():
        pass

@app.before_request
def before_request():
    # Initialize g.user and g.unread_count for all requests
    g.user = None
    g.unread_count = 0
    
    # Check if user is logged in
    if 'user_id' in session:
        db = get_db()
        g.user = db.execute('SELECT * FROM users WHERE id = ?', [session['user_id']]).fetchone()
        
        # Calculate unread count for both buyers and sellers
        if g.user:
            try:
                g.unread_count = get_unread_message_count(g.user[0], g.user[5])
            except Exception as e:
                g.unread_count = 0

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.user:
            flash('Please login to access this page', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    properties = get_properties()[:6]
    return render_template('index.html', properties=properties)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = get_user_by_username(username)
        
        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['user_type'] = user[5]
            flash('Login successful!', 'success')
            
            if user[5] == 'seller':
                return redirect(url_for('dashboard_seller'))
            else:
                return redirect(url_for('dashboard_buyer'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        email = request.form['email']
        phone = request.form['phone']
        user_type = request.form['user_type']
        
        try:
            user_id = insert_user(username, password, email, phone, user_type)
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists', 'error')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard/buyer')
def dashboard_buyer():
    if not g.user or g.user[5] != 'buyer':
        flash('Please login as a buyer', 'error')
        return redirect(url_for('login'))
    
    properties = get_properties()
    return render_template('dashboard_buyer.html', properties=properties)

@app.route('/dashboard/seller')
@login_required
def dashboard_seller():
    if g.user[5] != 'seller':
        flash('Access denied. This page is for sellers only.', 'danger')
        return redirect(url_for('dashboard_buyer'))
    
    properties = get_user_properties(g.user[0])
    return render_template('dashboard_seller.html', properties=properties)

@app.route('/property/add', methods=['GET', 'POST'])
def add_property():
    if not g.user or g.user[5] != 'seller':
        flash('Please login as a seller', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        location = request.form['location']
        property_type = request.form['property_type']
        sq_ft = float(request.form['sq_ft'])
        bedrooms = int(request.form['bedrooms'])
        bathrooms = int(request.form['bathrooms'])
        year_built = int(request.form['year_built'])
        parking_spaces = int(request.form['parking_spaces'])
        condition = request.form['condition']
        listing_type = request.form['listing_type'].strip().lower()
        
        # Predict price using ML model
        if listing_type == 'rent':
            from rent_model import predict_rent
            predicted_price = predict_rent(
                
                location=location,
                property_type=property_type,
                sq_ft=sq_ft,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                year_built=year_built,
                parking_spaces=parking_spaces,
                condition=condition
            )
        else:
            predicted_price = predict_price(
                location=location,
                property_type=property_type,
                sq_ft=sq_ft,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                year_built=year_built,
                parking_spaces=parking_spaces,
                condition=condition
            )
        
        if not predicted_price:
            predicted_price = 0
        
        image = request.files['image']
        if image and allowed_file(image.filename):
            filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{image.filename}"
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(image_path)
            image_path = f"images/properties/{filename}"
        else:
            image_path = "images/properties/default.jpg"
        
        insert_property(
            title=title,
            description=description,
            location=location,
            property_type=property_type,
            sq_ft=sq_ft,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            year_built=year_built,
            parking_spaces=parking_spaces,
            condition=condition,
            price=predicted_price,
            listing_type=listing_type,
            image_path=image_path,
            seller_id=g.user[0]
        )
        
        flash('Property added successfully!', 'success')
        return redirect(url_for('dashboard_seller'))
    
    return render_template('add_property.html')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

@app.route('/properties')
def properties():
    listing_type = request.args.get('type', None)
    location = request.args.get('location', None)
    property_type = request.args.get('property_type', None)
    bedrooms = request.args.get('bedrooms', None)
    price_range = request.args.get('price_range', None)
    
    properties = get_properties(
        listing_type=listing_type,
        location=location,
        property_type=property_type,
        bedrooms=bedrooms,
        price_range=price_range
    )
    
    return render_template('properties.html', 
                         properties=properties, 
                         listing_type=listing_type,
                         location=location,
                         property_type=property_type,
                         bedrooms=bedrooms,
                         price_range=price_range)

@app.route('/property/<int:property_id>')
def property_detail(property_id):
    if not g.user:
        flash('Please login to view property details', 'error')
        return redirect(url_for('login'))
        
    property = get_property_by_id(property_id)
    if not property:
        flash('Property not found', 'error')
        return redirect(url_for('properties'))
    return render_template('property_detail.html', property=property)

@app.route('/price-prediction', methods=['GET', 'POST'])
def price_prediction():
    if not g.user:
        flash('Please login to use price prediction', 'error')
        return redirect(url_for('login'))
        
    predicted_price = None
    prediction_type = None

    if request.method == 'POST':
        location = request.form['location']
        property_type = request.form['property_type']
        sq_ft = float(request.form['sq_ft'])
        bedrooms = int(request.form['bedrooms'])
        bathrooms = int(request.form['bathrooms'])
        year_built = int(request.form['year_built'])
        parking_spaces = int(request.form['parking_spaces'])
        condition = request.form['condition']
        prediction_type = request.form.get('prediction_type', 'sell')

        if prediction_type == 'rent':
            predicted_price = predict_rent(
                location, property_type, sq_ft, bedrooms, bathrooms,
                year_built, parking_spaces, condition
            )
        else:
            predicted_price = predict_price(
                location, property_type, sq_ft, bedrooms, bathrooms,
                year_built, parking_spaces, condition
            )

        if predicted_price is not None:
            flash_msg = f"Predicted {'Rent' if prediction_type == 'rent' else 'Price'}: ₹{predicted_price:,.2f}"
            flash(flash_msg, 'success')
        else:
            flash('Error in prediction. Please try again.', 'error')

    return render_template('price_prediction.html', predicted_price=predicted_price, prediction_type=prediction_type)

@app.route('/property/<int:property_id>/send-message', methods=['POST'])
def send_message(property_id):
    if not g.user:
        flash('Please login to send a message', 'error')
        return redirect(url_for('login'))
    
    property = get_property_by_id(property_id)
    if not property:
        flash('Property not found', 'error')
        return redirect(url_for('properties'))
    
    message = request.form.get('message')
    if not message:
        flash('Message cannot be empty', 'error')
        return redirect(url_for('property_detail', property_id=property_id))
    
    try:
        insert_message(
            property_id=property_id,
            sender_id=g.user[0],
            sender_name=g.user[1],  # username
            sender_email=g.user[3],  # email
            sender_phone=g.user[4],  # phone
            message=message
        )
        flash('Message sent successfully!', 'success')
    except Exception as e:
        flash('Error sending message. Please try again.', 'error')
    
    return redirect(url_for('property_detail', property_id=property_id))

@app.route('/messages')
@login_required
def messages():
    conversations = get_conversations_for_user(g.user[0], g.user[5])
    return render_template('messages.html', conversations=conversations)

@app.route('/conversation/<int:conversation_id>')
@login_required
def view_conversation(conversation_id):
    # Get conversation details
    db = get_db()
    cursor = db.cursor()
    
    # Verify user has access to this conversation
    cursor.execute('''
    SELECT c.*, p.title as property_title, p.location as property_location,
           CASE 
               WHEN ? = c.buyer_id THEN (SELECT username FROM users WHERE id = c.seller_id)
               ELSE (SELECT username FROM users WHERE id = c.buyer_id)
           END as other_party_name
    FROM conversations c
    JOIN properties p ON c.property_id = p.id
    WHERE c.id = ? AND (c.buyer_id = ? OR c.seller_id = ?)
    ''', [g.user[0], conversation_id, g.user[0], g.user[0]])
    
    conversation = cursor.fetchone()
    if not conversation:
        flash('Conversation not found', 'error')
        return redirect(url_for('messages'))
    
    # Get messages
    messages = get_messages_for_conversation(conversation_id)
    
    # Mark messages as read
    mark_conversation_messages_as_read(conversation_id, g.user[0])
    
    return render_template('conversation.html', 
                         conversation=conversation,
                         messages=messages)

@app.route('/conversation/<int:conversation_id>/send', methods=['POST'])
@login_required
def send_conversation_message(conversation_id):
    # Verify user has access to this conversation
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
    SELECT * FROM conversations 
    WHERE id = ? AND (buyer_id = ? OR seller_id = ?)
    ''', [conversation_id, g.user[0], g.user[0]])
    
    conversation = cursor.fetchone()
    if not conversation:
        flash('Conversation not found', 'error')
        return redirect(url_for('messages'))
    
    message = request.form.get('message')
    if not message:
        flash('Message cannot be empty', 'error')
        return redirect(url_for('view_conversation', conversation_id=conversation_id))
    
    try:
        # Insert message
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
        INSERT INTO messages (conversation_id, sender_id, message, created_at)
        VALUES (?, ?, ?, ?)
        ''', (conversation_id, g.user[0], message, current_time))
        
        # Update conversation's last_message_at
        cursor.execute('''
        UPDATE conversations 
        SET last_message_at = ? 
        WHERE id = ?
        ''', (current_time, conversation_id))
        
        db.commit()
        flash('Message sent successfully!', 'success')
    except Exception as e:
        flash('Error sending message. Please try again.', 'error')
    
    return redirect(url_for('view_conversation', conversation_id=conversation_id))

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)

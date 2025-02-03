# Import the necessary libraries
from flask import Flask, render_template, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from sqlalchemy import func
import pandas as pd
from io import BytesIO
from dateutil.relativedelta import relativedelta
import os

# Initialize the Flask app
app = Flask(__name__)
"""app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'"""
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
db = SQLAlchemy(app)

# Push an application context at startup
app.app_context().push()

# Each member details
class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    payment_date = db.Column(db.DateTime, nullable=False)
    amount_due = db.Column(db.Float, nullable=False)
    original_amount = db.Column(db.Float, nullable=False)  # Store the original amount
    payment_interval = db.Column(db.Integer, default=30)  # Default 30 days
    additional_details = db.Column(db.Text)

# Each payment details
class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'))
    payment_date = db.Column(db.DateTime, nullable=False)
    amount_paid = db.Column(db.Float, nullable=False)
    original_amount_due = db.Column(db.Float, nullable=False)  # Add this column

# Total reset details
class TotalReset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount_reset = db.Column(db.Float, nullable=False)
    reset_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

# Create the database tables
with app.app_context():
    db.create_all()

@app.route('/')
@app.route('/<int:page>')
def index(page=1):
    per_page = 50
    current_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Update payment dates and amounts for passed dates
    members = Member.query.all()
    for member in members:
        while member.payment_date < current_date:
            # Add the original amount to amount_due
            member.amount_due += member.original_amount
            # Calculate next payment date
            member.payment_date = member.payment_date + timedelta(days=member.payment_interval)
            
    db.session.commit()
    
    # Continue with existing pagination logic
    members = Member.query.order_by(Member.payment_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False)
    
    for member in members.items:
        # Calculate total payments for this member
        total_paid = db.session.query(func.sum(Payment.amount_paid))\
            .filter(Payment.member_id == member.id)\
            .scalar() or 0
        
        # Calculate remaining balance
        member.balance = member.amount_due - total_paid
    
    return render_template('index.html', members=members)

@app.route('/add_member', methods=['POST'])
def add_member():
    try:
        data = request.json
        print("Received data:", data)  # Debug print
        
        try:
            payment_date = datetime.strptime(data['payment_date'], '%Y-%m-%d')
            payment_date = payment_date.replace(hour=0, minute=0, second=0, microsecond=0)
        except ValueError as e:
            return jsonify({'success': False, 'error': f'Invalid date format: {str(e)}'})
            
        amount = float(data['amount_due'])
        current_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Always start with zero amount due; let the index route update it when the payment date has passed
        initial_amount_due = 0
        
        new_member = Member(
            name=data['name'],
            payment_date=payment_date,
            amount_due=initial_amount_due,  # Use calculated (zero) initial amount
            original_amount=amount,  # Always store the full amount
            payment_interval=data.get('payment_interval', 30),
            additional_details=data['additional_details']
        )
        db.session.add(new_member)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/get_member/<int:member_id>')
def get_member(member_id):
    member = Member.query.get_or_404(member_id)
    return jsonify({
        'name': member.name,
        'payment_date': member.payment_date.strftime('%Y-%m-%d'),
        'amount_due': member.amount_due,
        'original_amount': member.original_amount,
        'payment_interval': member.payment_interval,
        'additional_details': member.additional_details
    })

@app.route('/update_member/<int:member_id>', methods=['POST'])
def update_member(member_id):
    try:
        member = Member.query.get_or_404(member_id)
        data = request.json
        
        try:
            payment_date = datetime.strptime(data['payment_date'], '%Y-%m-%d')
            payment_date = payment_date.replace(hour=0, minute=0, second=0, microsecond=0)
        except ValueError as e:
            return jsonify({'success': False, 'error': f'Invalid date format: {str(e)}'})
        
        member.name = data['name']
        member.payment_date = payment_date
        member.amount_due = data['amount_due']
        member.original_amount = data['amount_due']  # Update original amount when amount_due is changed
        member.payment_interval = data.get('payment_interval', member.payment_interval)
        member.additional_details = data['additional_details']
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/delete_member/<int:member_id>', methods=['POST'])
def delete_member(member_id):
    try:
        member = Member.query.get_or_404(member_id)
        db.session.delete(member)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/payments')
def payments():
    # Calculate net collected amount
    total_payments = db.session.query(func.sum(Payment.amount_paid)).scalar() or 0
    total_resets = db.session.query(func.sum(TotalReset.amount_reset)).scalar() or 0
    net_collected = total_payments - total_resets
    
    # Calculate pending amount by summing the remaining amount_due from members
    pending_amount = db.session.query(func.sum(Member.amount_due)).scalar() or 0
    
    next_due = db.session.query(Member.payment_date)\
        .filter(Member.payment_date >= datetime.now())\
        .order_by(Member.payment_date)\
        .first()
    
    next_due_date = next_due[0].strftime('%d-%m-%Y') if next_due else 'No upcoming dues'
    
    # Get all members for the dropdown
    members = Member.query.order_by(Member.name).all()
    
    # Get today's date for the payment date field
    today_date = datetime.now().strftime('%Y-%m-%d')

    return render_template('payments.html',
                         total_collected=net_collected,
                         pending_amount=pending_amount,
                         next_due_date=next_due_date,
                         members=members,
                         today_date=today_date)

@app.route('/update_payment', methods=['POST'])
def update_payment():
    try:
        data = request.json
        payment_date = datetime.strptime(data['payment_date'], '%Y-%m-%d')
        
        # Get the member and their current total payments
        member = Member.query.get(data['member_id'])
        if not member:
            return jsonify({'success': False, 'error': 'Member not found'})
        
        # Create new payment record with original amount_due
        new_payment = Payment(
            member_id=data['member_id'],
            payment_date=payment_date,
            amount_paid=data['amount_paid'],
            original_amount_due=member.amount_due  # Store original amount before updating
        )
        
        # Add the payment record
        db.session.add(new_payment)
        
        # Update member's amount_due
        member.amount_due = max(0, member.amount_due - data['amount_paid'])
        
        db.session.commit()
        return jsonify({'success': True})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/reset_total/<type>', methods=['POST'])
def reset_total(type):
    try:
        if type == 'collected':
            # Get current total before reset
            current_total = db.session.query(func.sum(Payment.amount_paid)).scalar() or 0
            
            # Create reset record
            reset_record = TotalReset(
                amount_reset=current_total,
                reset_date=datetime.utcnow()
            )
            db.session.add(reset_record)
            db.session.commit()
            
            return jsonify({
                'success': True, 
                'total_collected': 0
            })
            
        elif type == 'pending':
            # Existing pending reset logic
            return jsonify({'success': True, 'pending_amount': 0})
            
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/set_next_due_date', methods=['POST'])
def set_next_due_date():
    try:
        data = request.json
        next_due_date = datetime.strptime(data['next_due_date'], '%Y-%m-%d')
        
        # Update all members' payment dates
        members = Member.query.all()
        for member in members:
            member.payment_date = next_due_date
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/export_payments')
def export_payments():
    try:
        # Query all payments with member information
        payments = db.session.query(
            Payment.id,
            Member.name,
            Member.payment_date.label('due_date'),
            Member.amount_due,
            Payment.amount_paid,
            Payment.payment_date
        ).join(Member).all()

        # Create DataFrame
        df = pd.DataFrame(payments, columns=[
            'Payment ID',
            'Member Name',
            'Payment Due Date',
            'Amount Due',
            'Amount Paid',
            'Payment Date'
        ])

        # Add Payment Status column
        df['Payment Status'] = df.apply(
            lambda x: 'Paid' if x['Amount Paid'] >= x['Amount Due'] else 'Partial' if x['Amount Paid'] > 0 else 'Unpaid',
            axis=1
        )

        # Format dates
        df['Payment Due Date'] = df['Payment Due Date'].dt.strftime('%d-%m-%Y')
        df['Payment Date'] = df['Payment Date'].dt.strftime('%d-%m-%Y')

        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Payments', index=False)
            
            # Get workbook and worksheet objects
            workbook = writer.book
            worksheet = writer.sheets['Payments']
            
            # Add basic formatting
            header_format = workbook.add_format({
                'bold': True,
                'border': 1
            })
            
            # Format headers and adjust column widths
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                worksheet.set_column(col_num, col_num, 15)

        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='payment_report.xlsx'
        )

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/reports')
def reports():
    # Get all members
    all_members = Member.query.order_by(Member.name).all()
    
    # Get total members
    total_members = Member.query.count()
    
    # Get total collected
    total_collected = db.session.query(func.sum(Payment.amount_paid)).scalar() or 0
    
    # Get pending payments
    pending_payments = db.session.query(func.sum(Member.amount_due)).scalar() or 0
    
    # Get overdue payments (payments past due date)
    overdue_payments = db.session.query(func.sum(Member.amount_due))\
        .filter(Member.payment_date < datetime.now())\
        .scalar() or 0
    
    # Get monthly revenue data for the chart (last 6 months)
    revenue_data = []
    revenue_labels = []
    for i in range(5, -1, -1):
        start_date = datetime.now() - relativedelta(months=i)
        end_date = start_date + relativedelta(months=1)
        monthly_revenue = db.session.query(func.sum(Payment.amount_paid))\
            .filter(Payment.payment_date >= start_date)\
            .filter(Payment.payment_date < end_date)\
            .scalar() or 0
        revenue_data.append(monthly_revenue)
        revenue_labels.append(start_date.strftime('%B %Y'))
    
    # Get payment status data for pie chart
    total_paid = db.session.query(func.sum(Payment.amount_paid)).scalar() or 0
    status_data = [total_paid, pending_payments]
    
    # Get recent transactions
    recent_transactions = db.session.query(
        Payment.id,
        Payment.payment_date,
        Member.name,
        Payment.amount_paid
    ).join(Member)\
    .order_by(Payment.payment_date.desc())\
    .limit(5)\
    .all()
    
    transactions_list = [{
        'id': txn.id,
        'date': txn.payment_date.strftime('%d-%m-%Y'),
        'member': txn.name,
        'amount': "%.2f" % txn.amount_paid,
        'status': 'Paid'
    } for txn in recent_transactions]
    
    return render_template('reports.html',
                         all_members=all_members,
                         total_members=total_members,
                         total_collected="%.2f" % total_collected,
                         pending_payments="%.2f" % pending_payments,
                         overdue_payments="%.2f" % overdue_payments,
                         revenue_labels=revenue_labels,
                         revenue_data=revenue_data,
                         status_data=status_data,
                         recent_transactions=transactions_list)

@app.route('/export_report')
def export_report():
    try:
        # Get date range from query parameters
        date_from = request.args.get('from')
        date_to = request.args.get('to')
        
        # Convert string dates to datetime objects
        from_date = datetime.strptime(date_from, '%Y-%m-%d') if date_from else None
        to_date = datetime.strptime(date_to, '%Y-%m-%d') if date_to else None
        
        # Query payments with date filter if dates are provided
        query = db.session.query(
            Payment.payment_date,
            Member.name,
            Member.amount_due,
            Payment.amount_paid
        ).join(Member)
        
        if from_date:
            query = query.filter(Payment.payment_date >= from_date)
        if to_date:
            query = query.filter(Payment.payment_date <= to_date)
            
        payments = query.order_by(Payment.payment_date.desc()).all()
        
        # Create DataFrame
        df = pd.DataFrame(payments, columns=[
            'Payment Date',
            'Member Name',
            'Amount Due',
            'Amount Paid'
        ])
        
        # Format dates
        df['Payment Date'] = df['Payment Date'].dt.strftime('%Y-%m-%d')
        
        # Add Payment Status column
        df['Payment Status'] = df.apply(
            lambda x: 'Paid' if x['Amount Paid'] >= x['Amount Due'] 
            else 'Partial' if x['Amount Paid'] > 0 
            else 'Unpaid',
            axis=1
        )
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Payment Report', index=False)
            
            # Get workbook and worksheet objects
            workbook = writer.book
            worksheet = writer.sheets['Payment Report']
            
            # Add formatting
            header_format = workbook.add_format({
                'bold': True,
                'border': 1,
                'bg_color': '#8A2BE2',
                'font_color': 'white'
            })
            
            # Format headers and adjust column widths
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                worksheet.set_column(col_num, col_num, 15)
        
        output.seek(0)
        
        # Generate filename with date range
        filename = f'payment_report_{date_from}_to_{date_to}.xlsx' if date_from and date_to else 'payment_report.xlsx'
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/get_member_details/<int:member_id>')
def get_member_details(member_id):
    member = Member.query.get_or_404(member_id)
    
    # Get all payments for this member
    payments = db.session.query(
        Payment.payment_date,
        Payment.amount_paid,
        Payment.original_amount_due,
        Member.name
    ).join(Member)\
    .filter(Payment.member_id == member_id)\
    .order_by(Payment.payment_date.desc())\
    .all()
    
    payment_history = [{
        'date': payment.payment_date.strftime('%Y-%m-%d'),
        'name': payment.name,
        'amount_paid': payment.amount_paid,
        'amount_due': payment.original_amount_due
    } for payment in payments]
    
    total_paid = sum(payment.amount_paid for payment in payments)
    
    return jsonify({
        'name': member.name,
        'total_due': member.amount_due,
        'total_paid': total_paid,
        'payments': payment_history
    })

@app.route('/get_transaction/<int:transaction_id>')
def get_transaction(transaction_id):
    try:
        # Query the transaction with member details
        transaction = db.session.query(
            Payment.id,
            Payment.payment_date,
            Payment.amount_paid,
            Member.id.label('member_id'),
            Member.name.label('member_name')
        ).join(Member)\
        .filter(Payment.id == transaction_id)\
        .first()

        if not transaction:
            return jsonify({'success': False, 'error': 'Transaction not found'}), 404

        return jsonify({
            'success': True,
            'transaction': {
                'id': transaction.id,
                'date': transaction.payment_date.strftime('%Y-%m-%d'),
                'amount': float(transaction.amount_paid),
                'member_id': transaction.member_id,
                'member_name': transaction.member_name
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/update_transaction/<int:transaction_id>', methods=['POST'])
def update_transaction(transaction_id):
    try:
        data = request.json
        payment = Payment.query.get_or_404(transaction_id)
        
        # Update payment details
        payment.payment_date = datetime.strptime(data['payment_date'], '%Y-%m-%d')
        payment.amount_paid = float(data['amount_paid'])
        
        # Update member's amount due
        member = Member.query.get(payment.member_id)
        if member:
            # Calculate the difference in payment
            payment_difference = float(data['amount_paid']) - payment.amount_paid
            member.amount_due = max(0, member.amount_due - payment_difference)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Transaction updated successfully'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/member_payment_history/<int:member_id>')
def member_payment_history(member_id):
    member = Member.query.get_or_404(member_id)
    
    # Get date filter parameters
    from_date = request.args.get('from')
    to_date = request.args.get('to')
    
    # Base query
    query = Payment.query.filter_by(member_id=member_id)
    
    # Apply date filters if provided
    if from_date and to_date:
        try:
            from_date = datetime.strptime(from_date, '%Y-%m-%d')
            to_date = datetime.strptime(to_date, '%Y-%m-%d')
            # Include the entire 'to_date' day by setting it to the end of the day
            to_date = to_date.replace(hour=23, minute=59, second=59)
            
            query = query.filter(
                Payment.payment_date >= from_date,
                Payment.payment_date <= to_date
            )
        except ValueError:
            # If date parsing fails, ignore the filters
            pass
    
    # Get payments ordered by date
    payments = query.order_by(Payment.payment_date.desc()).all()
    
    # Calculate total paid amount
    total_paid = sum(payment.amount_paid for payment in payments)
    
    return render_template('payment_history.html', 
                         member=member, 
                         payments=payments,
                         total_paid=total_paid)

#For gunicorn 
application = app

if __name__ == '__main__':
    app.run(debug=True)

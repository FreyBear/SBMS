# New Brew Task Routes - to replace dry hopping routes in app.py
# These routes handle scheduling and tracking of brew tasks
# (dry hopping, temperature changes, cold crash, bottling, kegging, etc.)

from datetime import datetime, date

@app.route('/brew/<int:brew_id>/task/add', methods=['GET', 'POST'])
@require_permission('brews', 'edit')
def add_brew_task(brew_id):
    """Add a brew task schedule to a brew"""
    from forms import AddBrewTaskForm
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html')
    
    # Verify brew exists
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, name FROM brew WHERE id = %s", (brew_id,))
            brew = cur.fetchone()
            
            if not brew:
                flash('Brew not found', 'error')
                return redirect(url_for('brews'))
            
            form = AddBrewTaskForm()
            
            if form.validate_on_submit():
                cur.execute("""
                    INSERT INTO brew_task (brew_id, scheduled_date, action, notes)
                    VALUES (%s, %s, %s, %s)
                """, (
                    brew_id,
                    form.scheduled_date.data,
                    form.action.data,
                    form.notes.data
                ))
                
                conn.commit()
                flash('Brew task added successfully!', 'success')
                return redirect(url_for('brew_detail', brew_id=brew_id))
    
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        conn.rollback()
    finally:
        conn.close()
    
    return render_template('add_brew_task.html', form=form, brew=brew)

@app.route('/brew-task/<int:task_id>/edit', methods=['GET', 'POST'])
@require_permission('brews', 'edit')
def edit_brew_task(task_id):
    """Edit or mark brew task as completed"""
    from forms import EditBrewTaskForm
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html')
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT bt.*, b.name as brew_name 
                FROM brew_task bt
                JOIN brew b ON bt.brew_id = b.id
                WHERE bt.id = %s
            """, (task_id,))
            
            task = cur.fetchone()
            if not task:
                flash('Brew task not found', 'error')
                return redirect(url_for('brews'))
            
            form = EditBrewTaskForm(obj=task)
            
            if form.validate_on_submit():
                # Set completed date if marking as completed
                completed_date = form.completed_date.data
                if form.is_completed.data and not completed_date:
                    completed_date = datetime.now().date()
                
                cur.execute("""
                    UPDATE brew_task
                    SET scheduled_date = %s,
                        completed_date = %s,
                        action = %s,
                        notes = %s,
                        is_completed = %s
                    WHERE id = %s
                """, (
                    form.scheduled_date.data,
                    completed_date,
                    form.action.data,
                    form.notes.data,
                    form.is_completed.data,
                    task_id
                ))
                
                conn.commit()
                flash('Brew task updated successfully!', 'success')
                return redirect(url_for('brew_detail', brew_id=task['brew_id']))
    
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        conn.rollback()
    finally:
        conn.close()
    
    return render_template('edit_brew_task.html', form=form, task=task)

@app.route('/brew-task/<int:task_id>/delete', methods=['POST'])
@require_permission('brews', 'edit')
def delete_brew_task(task_id):
    """Delete a brew task"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('brews'))
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get brew_id before deleting
            cur.execute("SELECT brew_id FROM brew_task WHERE id = %s", (task_id,))
            result = cur.fetchone()
            
            if not result:
                flash('Brew task not found', 'error')
                return redirect(url_for('brews'))
            
            brew_id = result['brew_id']
            
            cur.execute("DELETE FROM brew_task WHERE id = %s", (task_id,))
            conn.commit()
            
            flash('Brew task deleted successfully!', 'success')
            return redirect(url_for('brew_detail', brew_id=brew_id))
    
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        conn.rollback()
        return redirect(url_for('brews'))
    finally:
        conn.close()

# API Endpoints for AJAX operations

@app.route('/api/brew-task/add', methods=['POST'])
@require_permission('brews', 'edit')
def api_add_brew_task():
    """API endpoint to add brew task"""
    data = request.get_json()
    
    if not data or not all(k in data for k in ['brew_id', 'scheduled_date', 'action']):
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO brew_task (brew_id, scheduled_date, action, notes)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (
                data['brew_id'],
                data['scheduled_date'],
                data['action'],
                data.get('notes', '')
            ))
            
            task_id = cur.fetchone()['id']
            conn.commit()
            
            return jsonify({
                'success': True, 
                'message': 'Brew task added successfully',
                'task_id': task_id
            })
    
    except psycopg2.Error as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500
    finally:
        conn.close()

@app.route('/api/brew-task/<int:task_id>/edit', methods=['PUT'])
@require_permission('brews', 'edit')
def api_edit_brew_task(task_id):
    """API endpoint to edit brew task"""
    data = request.get_json()
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                UPDATE brew_task
                SET scheduled_date = COALESCE(%s, scheduled_date),
                    action = COALESCE(%s, action),
                    notes = COALESCE(%s, notes)
                WHERE id = %s
            """, (
                data.get('scheduled_date'),
                data.get('action'),
                data.get('notes'),
                task_id
            ))
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': 'Brew task updated successfully'
            })
    
    except psycopg2.Error as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500
    finally:
        conn.close()

@app.route('/api/brew-task/<int:task_id>/delete', methods=['DELETE'])
@require_permission('brews', 'edit')
def api_delete_brew_task(task_id):
    """API endpoint to delete brew task"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("DELETE FROM brew_task WHERE id = %s RETURNING id", (task_id,))
            result = cur.fetchone()
            
            if not result:
                return jsonify({'success': False, 'message': 'Brew task not found'}), 404
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': 'Brew task deleted successfully'
            })
    
    except psycopg2.Error as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500
    finally:
        conn.close()

@app.route('/api/brew-task/<int:task_id>/complete', methods=['POST'])
@require_permission('brews', 'edit')
def api_complete_brew_task(task_id):
    """API endpoint to mark brew task as completed"""
    data = request.get_json() or {}
    completed_date = data.get('completed_date', datetime.now().date())
    
    # Parse date if it's a string
    if isinstance(completed_date, str):
        try:
            completed_date = datetime.strptime(completed_date, '%Y-%m-%d').date()
        except:
            completed_date = datetime.now().date()
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get task details for validation
            cur.execute("""
                SELECT scheduled_date, is_completed 
                FROM brew_task 
                WHERE id = %s
            """, (task_id,))
            
            task = cur.fetchone()
            if not task:
                return jsonify({'success': False, 'message': 'Brew task not found'}), 404
            
            # Check if already completed
            if task['is_completed']:
                return jsonify({'success': False, 'message': 'Task is already marked as completed'}), 400
            
            # Warning if completed date is different from scheduled date
            date_warning = None
            if completed_date != task['scheduled_date']:
                days_diff = (completed_date - task['scheduled_date']).days
                if days_diff > 0:
                    date_warning = f'Task was scheduled for {task["scheduled_date"].strftime("%Y-%m-%d")} but marked complete {days_diff} days late'
                else:
                    date_warning = f'Task was scheduled for {task["scheduled_date"].strftime("%Y-%m-%d")} but marked complete {abs(days_diff)} days early'
            
            # Update the task
            cur.execute("""
                UPDATE brew_task
                SET is_completed = TRUE,
                    completed_date = %s
                WHERE id = %s
            """, (completed_date, task_id))
            
            conn.commit()
            
            response = {
                'success': True,
                'message': 'Brew task marked as completed'
            }
            
            if date_warning:
                response['warning'] = date_warning
            
            return jsonify(response)
    
    except psycopg2.Error as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500
    finally:
        conn.close()

@app.route('/api/brew-task/<int:task_id>/uncomplete', methods=['POST'])
@require_permission('brews', 'edit')
def api_uncomplete_brew_task(task_id):
    """API endpoint to mark brew task as NOT completed (undo completion)"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check if task exists
            cur.execute("SELECT is_completed FROM brew_task WHERE id = %s", (task_id,))
            task = cur.fetchone()
            
            if not task:
                return jsonify({'success': False, 'message': 'Brew task not found'}), 404
            
            if not task['is_completed']:
                return jsonify({'success': False, 'message': 'Task is not marked as completed'}), 400
            
            # Uncomplete the task
            cur.execute("""
                UPDATE brew_task
                SET is_completed = FALSE,
                    completed_date = NULL
                WHERE id = %s
            """, (task_id,))
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': 'Brew task unmarked as completed'
            })
    
    except psycopg2.Error as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500
    finally:
        conn.close()

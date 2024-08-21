from threading import Lock
from flask import Flask, render_template, session, request, \
    copy_current_request_context
from flask_socketio import SocketIO, emit, join_room, leave_room, \
    close_room, rooms, disconnect
import vxi11
import queue

dmmip = "10.10.60.124"
async_mode = None
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode=async_mode)
thread = None
thread_lock = Lock()
control_q = queue.Queue()

def dmm_vdc(instr):
    instr.write("CONF:VOLT:DC")
    instr.write("SAMP:COUN 1")
    instr.write("TRIG:COUN INF")
    instr.write("INIT")


def background_thread():
    count = 0
    instr =  vxi11.Instrument(dmmip)

    # init device
    while True:
        try:
            dmm_vdc(instr)
            break
        except:
            pass
    mode = "vdc"

    while True:
        if not control_q.empty():
            cmd = control_q.get_nowait()
            if cmd:
                if cmd == "vdc":
                    instr.write("CONF:VOLT:DC")
                    instr.write("SAMP:COUN 1")
                    instr.write("TRIG:COUN INF")
                    instr.write("INIT")
                if cmd == "cont":
                    instr.write("CONF:CONT")
                    instr.write("CONT:THR:VAL 2000")
                    instr.write("CONT:VOL:STAT HIGH")
                    instr.write("TRIG:COUN INF")
                    instr.write("INIT")
                mode = cmd
        data = instr.ask("DATA:LAST?")
        if mode == "vdc":
            data = data.split()
            v = float(data[0].split('E')[0])
            e = float(data[0].split('E')[1])
            data = v * (10 ** e)
            out = f'{data:.4}'
            socketio.emit('reading', {'data': out, 'unit': 'VDC'})
        if mode == "cont":
            data = float(data.split()[0])
            if data > 1000000000000:
                out = "open"
            else:
                out = f'{data:.4}'
            socketio.emit('reading', {'data': out, 'unit': 'Ω'})
        socketio.sleep(.15)
        count += 1

@app.route('/')
def index():
    return render_template('index.html', async_mode=socketio.async_mode)

@app.route('/control')
def controlpage():
    return render_template('control.html', async_mode=socketio.async_mode)

@socketio.event
def my_event(message):
    emit('my_response',
         {'data': message['data'], 'count': session['receive_count']})

@socketio.event
def control(message):
    control_q.put(message['type'])

@socketio.event
def connect():
    global thread
    with thread_lock:
        if thread is None:
            thread = socketio.start_background_task(background_thread)
    emit('my_response', {'data': 'Connected', 'count': 0})

if __name__ == '__main__':
    socketio.run(app, debug=True)

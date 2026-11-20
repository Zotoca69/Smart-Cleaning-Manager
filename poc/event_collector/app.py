"""Offline review UI. Synthetic transport only; no HA connections."""
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
import json, zipfile, hashlib, threading, queue, asyncio, time, base64
from collector import Store, request, capture
from unittest.mock import patch

class DemoSocket:
    def __init__(self, ids): self.ids=ids; self.step=0
    async def __aenter__(self): return self
    async def __aexit__(self,*args): pass
    async def send(self, raw): pass
    async def recv(self, **kwargs):
        self.step+=1
        messages=[{'type':'auth_required'},{'type':'auth_ok'}, {'id':1,'type':'result','success':True}, {'id':1,'type':'event','event':{'a':{i:{'s':'unknown'} for i in self.ids}}}]
        if self.step<=4: msg=messages[self.step-1]
        else:
            await asyncio.sleep(.1)
            msg={'id':1,'type':'event','event':{'c':{self.ids[0]:{'+':{'s':str(self.step)}}}}}
        return json.dumps(msg).encode()

async def demo(ids,path,seconds,stop,notify):
    with patch('collector.connect',return_value=DemoSocket(ids)):
        await capture('wss://synthetic.invalid','synthetic-only',ids,path,seconds,stop,notify)

def export(source, target):
    source=Path(source)
    manifest=(source/'manifest.json').read_bytes(); rows=(source/'messages.jsonl').read_bytes(); meta=json.loads(manifest)
    if hashlib.sha256(rows).hexdigest()!=meta['sha256']: raise ValueError('Capture hash mismatch')
    entries=rows.splitlines()
    if len(entries)!=meta['messages']: raise ValueError('Message count mismatch')
    for n,line in enumerate(entries,1):
        row=json.loads(line)
        if row['seq']!=n or hashlib.sha256(base64.b64decode(row['payload_b64'],validate=True)).hexdigest()!=row['sha256']: raise ValueError('Message integrity failure')
    with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED) as z:
        z.writestr('manifest.json',manifest); z.writestr('messages.jsonl',rows)

def main():
    root=tk.Tk(); root.title('HA Event Collector — offline review')
    tk.Label(root,text='Synthetic test mode — live HA disabled').pack(padx=20,pady=12)
    tk.Label(root,text='Exact entity IDs, one per line').pack(); entities=tk.Text(root,height=5,width=55); entities.pack(); entities.insert('1.0','sensor.example')
    tk.Label(root,text='Duration in seconds (1–900)').pack(); duration=tk.Entry(root); duration.insert(0,'10'); duration.pack()
    status=tk.StringVar(value='Ready'); tk.Label(root,textvariable=status).pack(pady=8)
    stop=threading.Event(); events=queue.Queue(); active=False; last=None
    def start():
        nonlocal active,last
        try:
            ids=entities.get('1.0','end').split(); request(ids); seconds=int(duration.get()); assert 1<=seconds<=900
        except (ValueError,AssertionError): messagebox.showerror('Invalid input','Check entities and duration'); return
        parent=filedialog.askdirectory(title='Choose private local folder')
        if not parent:return
        last=Path(parent)/('capture-'+str(time.time_ns())); stop.clear(); active=True; start_btn.config(state='disabled'); export_btn.config(state='disabled'); stop_btn.config(state='normal'); status.set('Collecting synthetic messages')
        def run():
            try: asyncio.run(demo(ids,last,seconds,stop,lambda n:events.put(('count',n))))
            except Exception as e: events.put(('done','Incomplete: '+type(e).__name__))
            else: events.put(('done','Capture stopped; inspect manifest'))
        threading.Thread(target=run,daemon=True).start()
    def choose():
        source=last or filedialog.askdirectory()
        if not source:return
        target=filedialog.asksaveasfilename(defaultextension='.zip')
        if not target:return
        try: export(source,target)
        except Exception as e: messagebox.showerror('Export failed',str(e))
        else: status.set('Archive created')
    def poll():
        nonlocal active
        while not events.empty():
            kind,value=events.get_nowait()
            if kind=='count': status.set(f'{value} messages')
            else: active=False; status.set(value); start_btn.config(state='normal'); export_btn.config(state='normal'); stop_btn.config(state='disabled')
        root.after(100,poll)
    def close():
        if active: stop.set(); root.after(200,close)
        else: root.destroy()
    start_btn=tk.Button(root,text='Start synthetic capture',command=start); start_btn.pack(pady=4)
    stop_btn=tk.Button(root,text='Stop',command=stop.set,state='disabled'); stop_btn.pack(pady=4)
    export_btn=tk.Button(root,text='Export capture',command=choose); export_btn.pack(pady=4)
    root.protocol('WM_DELETE_WINDOW',close); poll(); root.mainloop()
if __name__=='__main__':main()

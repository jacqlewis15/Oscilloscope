
# Jacqueline Lewis
# osc.py


# Setup instructions

# Make sure to install python module vxi11.
# > sudo pip install python-vxi11

# ip directions
# > hostname -I
# choose the ip address starting with 169
# change the instrument ip address to this number with a different 4th field
# i.e. pi says 169.254.5.136 -> for instrument use 169.254.5.1 etc.
#
# to change instrument ip address
# utility -> system i/o -> i/o -> change instrument settings


# This file documents a program to determine the lifetime of chemical 
# fluorescence when paired with an oscilloscope. The pi collects data
# from the oscilloscope and processes it to create viewable graphs.


import vxi11
from Tkinter import *
import Tkinter, Tkconstants, tkFileDialog
import math
import numpy as np
import os


##############################
# oscilloscope interfacing
##############################

# This function gets raw data from the oscilloscope.
def acquireData():
    # the instrument ip depends on the pi - see ip directions at top
    instr = vxi11.Instrument("169.254.5.1")
    instr.clear()
    # instrument query commands to get data limits
    instr.write(":DATA:SOURCE CH1;:DATA:START 1.0;:DATA:STOP 10000.0;")
    instr.write(":DATA:ENCDG ascii;:DATA:WIDTH 2;")
    instr.write("*WAI;:WFMPRE:YOFF?;:WFMPRE:YMULT?;:WFMPRE:YZERO?;:WFMPRE:XINCR?;:WFMPRE:XZERO?")
    limits = str(instr.read(num=1024)).split(";")
    # instrument query command to get data points
    instr.write("CURVE?")
    data = ""
    # gets all points
    while(len(data.split(",")) < 10000):
        data += str(instr.read(num=4096))
    return limits, data.split(",")

# This function reads the raw limit data from the oscilloscope.
def readLimit(limit):
    splt = limit.split("E")
    if len(splt) > 1:
        return float(splt[0]) * (10.0 ** float(splt[1]))
    else:
        return float(limit)

# This function reads the raw data points and converts them using
# the provided limits.
def readDatum(limits):
    yoff, ymult, yzero, xincr, xzero = limits
    return (lambda x: round((float(x)-yoff)*ymult + yzero, 8))

# This function provides the time data points.
def buildPoints(limits, data):
    yoff, ymult, yzero, xincr, xzero = limits
    lst = []
    for i in range(len(data)):
        lst.append((round(xzero + xincr * i, 8), data[i]))
    return lst

# This function determines the min max data points.
def getEdges(points):
    ymin = ymax = points[0][1]
    for (x,y) in points:
        if y < ymin: ymin = y
        if y > ymax: ymax = y
    return (0,points[-1][0]),(ymin,ymax)

# This function connects all interfacing functions to return
# readable data points and limits.
def getData():
    limits, data = acquireData()
    limits = map(readLimit, limits)
    data = map(readDatum(limits), data)
    points = buildPoints(limits, data)
    xlim,ylim = getEdges(points)
    return points,xlim,ylim


# extra functions

# This function returns the log of all acceptable inputs,
# otherwise it returns None.
def safeLog(x):
    if x > 0: return math.log(x)
    else: return None

# This function computes the log data point.
def yLog(point):
    x,y = point
    return (x,safeLog(y))

# from 15-112, This function writes contents to a file.
def writeFile(path, contents):
    with open(path, "wt") as f:
        f.write(contents)


################################
######### GRAPH CLASS ##########
################################

# This class defines the interface to a tkinter graph, with
# boundaries defined by the coordinates, and all other graph
# data defined as labeled.
class Graph(object):

    def __init__(self,xlim,ylim,xaxis,yaxis,points,title,coord):
        self.xlim = xlim # bounds on x data
        self.ylim = ylim # bounds on y data
        self.xaxis = xaxis # x axis label
        self.yaxis = yaxis # y axis label
        self.points = points # data points
        self.title = title # graph title
        self.coord = coord # tkinter graph space edges
        self.margin = 20
        self.limits() # tkinter graph edges
        self.scales() # conversion from data to tkinter space

    # This function determines the edges of the graph in the given
    # tkinter space.
    def limits(self):
        x1,y1,x2,y2 = self.coord
        self.axisLimits = (x1+self.margin*3,y1+self.margin,
            x2-self.margin,y2-self.margin*3)

    # This function determines the scaling factor from data point
    # to tkinter space for graphing.
    def scales(self):
        x1,y1,x2,y2 = self.axisLimits
        LB,UB = self.xlim
        self.xscale = (x2-x1)/float(UB-LB)
        LB,UB = self.ylim
        self.yscale = (y2-y1)/float(UB-LB)

    # This function converts a data point to a coordinate space
    # point.
    def getCoord(self,point):
        x,y = point
        xcoord = (x-self.xlim[0])*self.xscale+self.axisLimits[0]
        ycoord = (self.ylim[1]-y)*self.yscale+self.axisLimits[1]
        return xcoord,ycoord

    # This function converts a coordinate space point to a data
    # point.
    def getPoint(self,point):
        x,y = point
        xcoord = (x-self.axisLimits[0])/self.xscale+self.xlim[0]
        ycoord = self.ylim[1]-(y-self.axisLimits[1])/self.yscale
        return xcoord,ycoord

    # This function adds a new point to the data points.
    def addPoint(self,point):
        self.points.append(point)

    # This function updates the x and y limits of the data,
    # changing the scaling factor.
    def updateLimits(self,xlim,ylim):
        self.xlim = xlim
        self.ylim = ylim
        self.scales()

    # This function determines if a graph is empty.
    def isEmpty(self):
        return self.points == []

    # This function checks if a coordinate point is within 
    # the graph sapce.
    def inGraph(self,x,y):
        return (self.axisLimits[0] < x < self.axisLimits[2] and
            self.axisLimits[1] < y < self.axisLimits[3])

    # This function makes a log graph from a linear graph.
    def makeLogGraph(self, data):
        # This function checks if a point is within bounds.
        def inBound(point):
            x,y = point
            # if the bound isn't set, all points are in
            if data.bound[0] != None:
                if data.lb > x: return False
            if data.bound[1] != None:
                if data.ub < x: return False
            return True
        # This function gets the correct value out of a tuple.
        def getTuple(point,idx):
            return point[idx]
        # This function checks if a value is None.
        def notNone(point):
            x,y = point
            return y != None
        # gets the points in the log graph
        points = filter(notNone, map(yLog, filter(inBound,self.points)))
        ys = map(lambda x: getTuple(x,1), points)
        xs = map(lambda x: getTuple(x,0), points)
        ylow,xlow = min(ys),min(xs)
        yup,xup = max(ys),max(xs)
        # finds the lifetime of the data
        linReg(data,xs,ys)
        return Graph((xlow,xup),(ylow,yup),self.xaxis,self.yaxis,points,
            self.title,self.coord)

    # This function draws the graph.
    def drawGraph(self,canvas):
        canvas.create_rectangle(self.axisLimits,fill="white")
        self.drawAxes(canvas)
        self.drawPoints(canvas)
        self.drawLabels(canvas)

    # This function draws the graph axes, with numberings.
    def drawAxes(self,canvas):

        # y axes, in volts
        xl,yl,xu,yu = self.axisLimits
        # creates horizontal grid lines
        for i in range(5):
            x1,y1 = xl,yl+i*(yu-yl)/4.0
            x2,y2 = xu,yl+i*(yu-yl)/4.0
            # determines graph marking
            val = round(self.ylim[1]-(self.ylim[1]-self.ylim[0])/4.0*i,2)
            canvas.create_line(x1,y1,x2,y2)
            canvas.create_text(self.axisLimits[0]-5,y2,anchor="e",text=str(val))
        
        # x axes, in ns
        xl,yl,xu,yu = self.axisLimits
        # creates vertical grid lines
        for i in range(5):
            x1,y1 = xl+i*(xu-xl)/4.0,yl
            x2,y2 = xl+i*(xu-xl)/4.0,yu
            # determines graph marking
            val = int((self.xlim[0]+(self.xlim[1]-self.xlim[0])/4.0*i)*10**9)
            canvas.create_line(x1,y1,x2,y2)
            canvas.create_text(x2,y2+20,anchor="n",text=str(val),angle=90)

    # This function draws the points on the graph.
    def drawPoints(self,canvas):
        for point in self.points:
            x,y = self.getCoord(point)
            if y == None: continue
            x1,y1 = x-2,y-2
            x2,y2 = x+2,y+2
            canvas.create_oval(x1,y1,x2,y2,fill="black")

    # This function draws the graph labels.
    def drawLabels(self,canvas):
        x1,y1,x2,y2 = self.coord
        canvas.create_text((x2-x1)/2+x1,y1+5,text=self.title,
            font="Arial 15 bold")
        canvas.create_text((x2-x1)/2+x1,y2-5,text=self.xaxis,
            font = "Arial 12 bold")
        canvas.create_text(x1+5,(y2-y1)/2+y1,text=self.yaxis,
            font = "Arial 12 bold",angle=90)


####################################
# UI
####################################

# This function determines the lifetime and r2 value for
# the log graph.
def linReg(data,x1,y1):
    # converts data to solver format
    x = np.array(x1)
    y = np.array(y1)
    n = np.size(x)
    # calculates slope
    m_x,m_y = np.mean(x),np.mean(y)
    SS_xy = np.sum(y*x) - n*m_y*m_x
    SS_xx = np.sum(x*x) - n*m_x*m_x
    b_1 = SS_xy / SS_xx
    b_0 = m_y - b_1*m_x
    data.yint = b_0
    data.slope = b_1
    # calculates r2
    yhat = np.array(map(lambda x: b_1*x+b_0,x1))
    SSR = np.sum((yhat-m_y)**2)
    SSTO = np.sum((y-m_y)**2)
    data.r2 = SSR/SSTO
    data.lifetime = -(10**9)/b_1

# This function creates an empty V vs. t graph.
def emptyGraph(data):
    return Graph((0,0.0000001),(0,1),"Time (ns)","Voltage (V)",
        [],"Voltage vs. Time",(data.margin,data.height/3+data.margin,
            data.width-data.margin,data.height-data.margin))

# This function initializes the data that changes each time
# that new data is requested.
def plotInit(data):
    data.margin = 5
    data.mode = "plot"
    data.graph = emptyGraph(data)
    data.logGraph = emptyGraph(data)
    data.log = False
    data.edit = [False,False,[False]*8,[False]*12,[False]*2]
    data.slope = 0
    data.yint = 0
    data.r2 = 0
    data.selected = (None,None)
    data.highlight = (None,None)

# This function creates a 96 well grid of white space 
# iteratively to avoid aliasing.
def initGrid():
    grid = []
    for j in range(8):
        row = []
        for i in range(12):
            row.append("white")
        grid.append(row)
    return grid

# This function is the program initialization.
def init(data):
    plotInit(data)
    # persistent information
    data.name = ""
    data.foldName = ""
    data.pipe = False
    data.time = 0
    data.lb = 0
    data.ub = 0
    data.bound = [None,None]
    # for save mode
    data.color = initGrid()
    data.colName = map(str,range(1,13))
    data.rowName = map(str,range(1,9))
    data.header = ["NN","CN"]
    data.last = (None,None)

# This function binary searches for an x coordinate in
# a list of tuples, returning the y coordinate.
def search(lst, elem):
    # base cases
    if len(lst) == 0: return None
    elif len(lst) == 1:
        x,y = lst[0]
        if x == elem: return y
    # recursive case
    else: # check midpoint
        x,y = lst[len(lst)//2]
        if x == elem: return y
        elif x < elem: return search(lst[len(lst)//2+1:],elem)
        elif x > elem: return search(lst[:len(lst)//2-1],elem)

# This function responds to button clicks in the left column.
def pressLeft(canvas, data, index):
    if index == 0: # new data button
        # prints status to show that it's computing
        canvas.create_text(data.width/2,20,text="Getting New Data",
            font="Arial 20 bold")
        plotInit(data)
        canvas.update()
        points,xlim,ylim = getData()
        # creates a new graph with the new data
        data.graph = Graph(xlim,ylim,"Time (s)","Voltage (V)",
        points,"Voltage vs. Time",(data.margin,
            data.height/3+data.margin,data.width-data.margin,
                data.height-data.margin))
    elif index ==1: # save button on log plot
        if data.log: data.mode = "save"
    elif index ==2: # set lower bound on linear plot
        if not data.log: data.edit[0] = True

# This function responds to button clicks in the right column.
def pressRight(canvas, data, index):
    if index == 0: # switches between log and linear plot.
        if data.log: 
            # prints status to show that it's computing
            canvas.create_text(data.width/2,20,text="Showing Linear Plot",
                font="Arial 20 bold")
            canvas.update()
            data.log = False
        else: 
            # prints status to show that it's computing
            canvas.create_text(data.width/2,20,text="Showing Log Plot",
                font="Arial 20 bold")
            canvas.update()
            data.log = True
            # only computes a new log graph when necessary
            if (data.logGraph.isEmpty() or 
                    (data.logGraph.xlim != (data.lb,data.ub))):
                data.logGraph = data.graph.makeLogGraph(data)
    elif index ==1: pass # not a button
    elif index ==2: # set upper bound on linear plot
        if not data.log: data.edit[1] = True

# This function determines the bounds of the graph as
# set by mouse clicks.
def boundLine(data, x):
    if data.edit[0]:
        # finds the x point in graph units
        data.lb = data.graph.getPoint((x,0))[0]
        data.bound[0] = x
        data.edit[0] = False
    elif data.edit[1]:
        # finds the x point in graph units
        data.ub = data.graph.getPoint((x,0))[0]
        data.bound[1] = x
        data.edit[1] = False

# This function responds to mouse clicks in "plot" mode.
def plotMousePressed(event,canvas,data): 
    bwidth = data.width/3
    bheight = data.height/3/7
    # left column clicks
    if bwidth/3 < event.x < 4*bwidth/3:
        if bheight < event.y < bheight*2: pressLeft(canvas,data,0)
        elif bheight*3 < event.y < bheight*4: pressLeft(canvas,data,1)
        elif bheight*5 < event.y < bheight*6: pressLeft(canvas,data,2)
    # right column clicks
    elif 5*bwidth/3 < event.x < 8*bwidth/3:
        if bheight < event.y < bheight*2: pressRight(canvas,data,0)
        elif bheight*3 < event.y < bheight*4: pressRight(canvas,data,1)
        elif bheight*5 < event.y < bheight*6: pressRight(canvas,data,2)
    # graph clicks
    if (data.edit[0] or data.edit[1]) and data.graph.inGraph(event.x,event.y):
        boundLine(data,event.x)

def plotMouseMotion(event,data): pass

def plotKeyPressed(event,data): pass

def plotTimerFired(data): pass

# This function draws all the buttons in "plot" mode.
def drawButtons(data,canvas): 
    bwidth = data.width/3
    bheight = data.height/3/7
    # draws 6 buttons, 2 columns
    for i in range(2):
        for j in range(3):
            x1 = bwidth/3*(i+1)+i*bwidth
            y1 = bheight*(2*j+1)
            x2 = bwidth/3*(i+1)+(i+1)*bwidth
            y2 = bheight*(2*j+2)
            canvas.create_rectangle(x1,y1,x2,y2,fill="white")
            # each button has specific text
            fill = "black" 
            if i == 0 and j == 0: text = "New Data"
            elif i == 1 and j == 0: 
                if data.log: text = "Show Linear Plot"
                else: text = "Show Log Plot"
            elif i == 0 and j == 1: 
                if data.log:
                    text = "Save"
                else: # conversion from s to ns
                    text = "LB (ns): " + str(round(data.lb*10**9,2))
            elif i == 1 and j == 1: 
                if data.log:
                    text = "lifetime (ns): %8.4f" % data.lifetime
                else: # conversion of s to ns
                    text = "UB (ns): " + str(round(data.ub*10**9,2))
            elif i == 0 and j == 2: 
                if data.log:
                    text = "y-int: %8f" % data.yint
                else:
                    text = "Set Lower Bound"
                    if data.edit[0]: fill = "red"
            elif i == 1 and j == 2: 
                if data.log:
                    text = "r^2: %8f" % data.r2
                else:
                    text = "Set Upper Bound"
                    if data.edit[1]: fill = "red"
            canvas.create_text(x1+5,y1+5,anchor="nw",font="Arial 18 bold",
                text=text,fill=fill)

# This function draws the boundary lines on the graph.
def drawBoundLines(data, canvas):
    if not data.log:
        if data.bound[0] != None:
            canvas.create_line(data.bound[0],data.graph.axisLimits[1],
                data.bound[0],data.graph.axisLimits[3],fill="light green",width="2")
        if data.bound[1] != None:
            canvas.create_line(data.bound[1],data.graph.axisLimits[1],
                data.bound[1],data.graph.axisLimits[3],fill="red",width="2")

# This function dispatches the drawing functions for "plot" mode.
def plotRedrawAll(canvas,data):
    canvas.create_rectangle(-5,-5,data.width+5,data.height+5,fill="lightblue")
    if data.log: data.logGraph.drawGraph(canvas)
    else: data.graph.drawGraph(canvas)
    drawBoundLines(data,canvas)
    drawButtons(data,canvas)


####################################
# save mode #
####################################


# This function saves the data to a txt file.
def save(data): 
    name = data.name
    foldName = data.foldName
    fileName = foldName + "/" + name + ".txt"
    # comma-separates all data for processing by mathematica
    contents = str(data.lifetime) + ",\n" + str(data.r2) + ",\n"
    for i in range(len(data.logGraph.points)):
        x,z = data.logGraph.points[i]
        y = search(data.graph.points, x)
        line = str(x) + "," + str(y) + "," + str(z) + "\n"
        contents += line
    writeFile(fileName, contents)

# This function returns the name of the file (not the whole path) without 
# its "." ending.
def trimFileName(fileName):
    return fileName.split("/")[-1].split(".")[0]

# This function gets a file from the directory.
def folderExplorer(data):
    location = os.getcwd()
    name = tkFileDialog.askdirectory()
    if name == (): name = ""
    return name

# This function reacts button presses in save mode.
def savePress(canvas, data, i):
    if i == 0: # return button
        data.mode = "plot"
        for j in range(2,4):
            for i in range(len(data.edit[j])):
                data.edit[j][i] = False
    if i == 1: # folder name button
        data.foldName = folderExplorer(data)
        data.color = initGrid()
        data.last = data.selected = (None,None)
        data.name = ""
    if i == 2: pass # name
    if i == 3: # save button
        # ensures all necessary data is entered
        if data.name != "" and data.foldName != "":
            # prints status to show that it's computing
            canvas.create_text(data.width/2,20,text="Saving",
                font="Arial 20 bold")
            canvas.update()
            save(data)
            data.mode = "plot"
            row,col = data.selected
            data.color[row][col] = "green"
            data.last = data.selected
            data.selected = (None,None)

# This function reacts to mouse licks in save mode.
def saveMousePressed(event,canvas,data): 
    (bwidth,bheight,margin,top,bot,left,right,squarewidth,namewidth,
        squareheight,nameheight) = gridVals(data)
    # checks if a button was pressed
    bLeft = left
    bRight = bLeft+bwidth
    # button press in top left column
    if bLeft < event.x < bRight:
        for i in range(4):
            t = bheight + (2*i)*bheight
            b = t + bheight
            if t < event.y < b:
                savePress(canvas, data, i)
    # button press in left grid column
    if left < event.x < left+namewidth:
        if top+nameheight < event.y < bot:
            i = (event.y-nameheight-top)//squareheight
            if True not in data.edit[2] and True not in data.edit[3]: 
                data.edit[2][i] = True
    # button press in top grid row
    if left+namewidth < event.x < right:
        if top < event.y < top+nameheight:
            i = (event.x-left-namewidth)//squarewidth
            if True not in data.edit[2] and True not in data.edit[3]: 
                data.edit[3][i] = True
    # button press in header edit square
    if left < event.x < left+namewidth:
        if top < event.y < top+nameheight:
            # button press in column header triangle
            if event.x-left > event.y-top: data.edit[4][1] = True
            # button press in row header triangle
            else: data.edit[4][0] = True
    # button press in main grid
    if left+namewidth < event.x < right:
        if top+nameheight < event.y < bot:
            letters = ["A","B","C","D","E","F","G","H"]
            row = (event.y-top-nameheight)//squareheight
            col = (event.x-left-namewidth)//squarewidth
            data.selected = (row,col)
            data.name = (letters[row] + "%02d-" + data.header[0] + 
                data.rowName[row] + data.header[1] + data.colName[col]) % (col+1)

# This function reacts to user mouseover in the grid region.
def saveMouseMotion(event,data): 
    (bwidth,bheight,margin,top,bot,left,right,squarewidth,namewidth,
        squareheight,nameheight) = gridVals(data)
    # finds the row and column moused over to highlight them
    data.highlight = (None,None)
    if left+namewidth < event.x < right:
        if top+nameheight < event.y < bot:
            row = (event.y-top-nameheight)//squareheight
            col = (event.x-left-namewidth)//squarewidth
            data.highlight = (row,col)

# This function responds to key stroked in save mode.
def saveKeyPressed(event,data): 
    # edits the row labels
    if True in data.edit[2]:
        i = data.edit[2].index(True)
        if event.keysym == "Return": # ends edit
            data.edit[2][i] = False
            data.pipe = False
        elif event.keysym == "BackSpace": data.rowName[i] = data.rowName[i][:-1]
        else: data.rowName[i] += event.char
    # edits the col labels
    elif True in data.edit[3]:
        i = data.edit[3].index(True)
        if event.keysym == "Return": # ends edit
            data.edit[3][i] = False
            data.pipe = False
        elif event.keysym == "BackSpace": data.colName[i] = data.colName[i][:-1]
        else: data.colName[i] += event.char
    # edits the row/col header names
    elif True in data.edit[4]:
        i = data.edit[4].index(True)
        if event.keysym == "Return": # ends edit
            data.edit[4][i] = False
            data.pipe = False
        elif event.keysym == "BackSpace": data.header[i] = data.header[i][:-1]
        else: data.header[i] += event.char.upper()

# This function reacts to lengths of time in save mode.
def saveTimerFired(data): 
    # updates blinking cursor in edit mode
    if data.time % 5 == 0 and (True in data.edit[2]
        or True in data.edit[3] or True in data.edit[4]): 
        data.pipe = not data.pipe
    data.time += 1

# This function interprets true/false as a character for a cursor.
def piping(pipe):
    if pipe: return "|"
    else: return ""

# This function draws the buttons on the save screen.
def drawSaveButtons(canvas,data):

    bwidth = data.width/2
    bheight = data.height/12/2
    margin = 20
    left = margin
    right = left + bwidth
    # four buttons
    for i in range(4):
        top = bheight + (2*i)*bheight
        bottom = top + bheight
        canvas.create_rectangle(left,top,right,bottom,fill="white")
        if i == 0: text = "Return"
        if i == 1: text = "Folder Name: " + trimFileName(data.foldName)
        if i == 2: text = "Name: " + data.name
        if i == 3: text = "Save"
        canvas.create_text(left+bwidth/2,top+bheight/2,text=text,
            font="Arial 18 bold")

# This function sets the constants used in the grid.
def gridVals(data):
    # top portion of screen
    bwidth = data.width/2
    bheight = data.height/12/2
    margin = 20
    top = 9*bheight
    # grid constants
    bot = data.height-margin
    left = margin
    right = data.width-margin
    squarewidth = (right-left)//13
    namewidth = right-left-12*squarewidth
    squareheight = (bot-top)//9
    nameheight = bot-top-8*squareheight
    return (bwidth,bheight,margin,top,bot,left,right,
        squarewidth,namewidth,squareheight,nameheight)

# This function determines a highlight color for the affected
# regions.
def highlight(color):
    if color == "white": return "pink"
    elif color == "green": return "light green"
    else: return color

# This function draws the grid of nn and cn combinations.
def drawGrid(canvas,data):
    (bwidth,bheight,margin,top,bot,left,right,squarewidth,namewidth,
        squareheight,nameheight) = gridVals(data)
    canvas.create_rectangle(left,top,right,bot,fill="white")
    # draws each grid square with proper coloration
    for i in range(12):
        for j in range(8):
            l = left+namewidth+i*squarewidth
            t = top+nameheight+j*squareheight
            fill = data.color[j][i]
            # adds special colors for certain tiles
            if data.last == (j,i): fill = "yellow"
            if data.selected == (j,i): fill = "red"
            if data.highlight[0] == j or data.highlight[1] == i:
                fill = highlight(fill)
            canvas.create_rectangle(l,t,l+squarewidth,t+squareheight,
                fill=fill)

# This function draws the legend for the grid at the top right
# of the screen.
def legend(canvas,data):
    (bwidth,bheight,margin,top,bot,left,right,squarewidth,namewidth,
        squareheight,nameheight) = gridVals(data)
    # three labels, for the main colors used
    space = (top-3*squareheight)/4
    l = right-squarewidth
    for i in range(3):
        if i == 0: 
            fill = "white"
            text = "No data"
        if i == 1: 
            fill = "green"
            text = "Collected"
        if i == 2: 
            fill = "yellow"
            text = "Last collected"
        # draws and labels square
        canvas.create_rectangle(l,i*squareheight+(i+1)*space,l+squarewidth,
            (i+1)*squareheight+(i+1)*space,fill=fill)
        canvas.create_text(l-5,(i+.5)*squareheight+(i+1)*space,anchor="e",
            text=text,font="Arial 18 bold")

# This function adds the numbering system to the grid.
def labelGrid(canvas,data):
    (bwidth,bheight,margin,top,bot,left,right,squarewidth,namewidth,
        squareheight,nameheight) = gridVals(data)
    # draws top left labels and line
    canvas.create_line(left,top,left+namewidth,top+nameheight)
    text = data.header[1] + piping(data.edit[4][1] and data.pipe)
    canvas.create_text(left+namewidth-5,top+5,anchor="ne",text=text,
        font="Arial 15 bold")
    text = data.header[0] + piping(data.edit[4][0] and data.pipe)
    canvas.create_text(left+5,top+nameheight-5,anchor="sw",text=text,
        font="Arial 15 bold")
    # draws top labels and lines
    for i in range(12):
        l = left+namewidth+i*squarewidth
        canvas.create_line(l,top,l,top+nameheight)
        text = data.colName[i] + piping(data.edit[3][i] and data.pipe)
        canvas.create_text(l+squarewidth/2,top+nameheight/2,
            font="Arial 15 bold",text=text)
    # draws left labels and lines
    for i in range(8):
        t = top+nameheight+i*squareheight
        canvas.create_line(left,t,left+namewidth,t)
        text = data.rowName[i] + piping(data.edit[2][i] and data.pipe)
        canvas.create_text(left+namewidth/2,t+squareheight/2,
            font="Arial 15 bold",text=text)

# This function draws the save screen.
def saveRedrawAll(canvas,data):
    canvas.create_rectangle(-5,-5,data.width+5,data.height+5,fill="lightblue")
    drawSaveButtons(canvas,data)
    drawGrid(canvas,data)
    labelGrid(canvas,data)
    legend(canvas,data)

####################################
# dispatcher #
####################################

# These functions dispatch commands based on the mode.

def mousePressed(event,canvas,data):
    if data.mode == "save": saveMousePressed(event,canvas,data)
    elif data.mode == "plot": plotMousePressed(event,canvas,data)

def mouseMotion(event,data):
    if data.mode == "save": saveMouseMotion(event,data)
    elif data.mode == "plot": plotMouseMotion(event,data)

def keyPressed(event,data): 
    if data.mode == "save": saveKeyPressed(event,data)
    elif data.mode == "plot": plotKeyPressed(event,data)

def timerFired(data): 
    if data.mode == "save": saveTimerFired(data)
    elif data.mode == "plot": plotTimerFired(data)

def redrawAll(canvas,data):
    if data.mode == "save": saveRedrawAll(canvas,data)
    elif data.mode == "plot": plotRedrawAll(canvas,data)

####################################
# runUI function # from 15-112 #
####################################

def runUI(width=300, height=300):
    def redrawAllWrapper(canvas, data):
        canvas.delete(ALL)
        redrawAll(canvas, data)
        canvas.update()    

    def mousePressedWrapper(event, canvas, data):
        mousePressed(event, canvas, data)
        redrawAllWrapper(canvas, data)

    def mouseMotionWrapper(event,canvas,data):
        mouseMotion(event,data)
        redrawAllWrapper(canvas,data)

    def keyPressedWrapper(event, canvas, data):
        keyPressed(event, data)
        redrawAllWrapper(canvas, data)

    def timerFiredWrapper(canvas, data):
        timerFired(data)
        redrawAllWrapper(canvas, data)
        # pause, then call timerFired again
        canvas.after(data.timerDelay, timerFiredWrapper, canvas, data)
    # Set up data and call init
    class Struct(object): pass
    data = Struct()
    data.width = width
    data.height = height
    data.timerDelay = 100 # milliseconds
    init(data)
    # create the root and the canvas
    root = Tk()
    canvas = Canvas(root, width=data.width, height=data.height)
    canvas.pack()
    # set up events
    root.bind("<Button-1>", lambda event:
                            mousePressedWrapper(event, canvas, data))
    root.bind("<Key>", lambda event:
                            keyPressedWrapper(event, canvas, data))
    root.bind("<Motion>", lambda event: 
                            mouseMotionWrapper(event, canvas, data))
    timerFiredWrapper(canvas, data)
    # and launch the app
    root.mainloop()  # blocks until window is closed

runUI(800,800)

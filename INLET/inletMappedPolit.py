import numpy as np
import re, os, glob

# Function to get face normal vectors from three points 
def getFaceNormalVectors(p1, p2, p3, orintation='in'):
    # Get vectors from p1 to p2 and p1 to p3
    v1 = p2 - p1
    v2 = p3 - p1
    # Get cross product of vectors
    v3 = np.cross(v1, v2)
    # Normalize vector
    v3 = v3 / np.linalg.norm(v3)
    # Check orientation in or out
    if orintation == 'in':
        # z direction is negative
        if v3[2] > 0:
            v3 = -v3
    elif orintation == 'out':
        # z direction is positive
        if v3[2] < 0:
            v3 = -v3
    return v3

# Function to read csv file return time and velcity data
def readCSVFile(fileName):
    # Read csv file
    data = np.genfromtxt(fileName, delimiter=' ', skip_header=0)
    # Get time and velocity data
    time = data[:,0]
    vel = data[:,1]
    return time, vel

# Function to get velocity x, y and z components from velocity magnitude and face normal vectors
def getVelocityComponents(vel, faceNormalVectors):
    # Get velocity x, y and z components
    velX = vel * faceNormalVectors[0]
    velY = vel * faceNormalVectors[1]
    velZ = vel * faceNormalVectors[2]
    return velX, velY, velZ

# Funtion to read openfoam points file and return points in scaled 10^-3
def readPointsFile(fileName):
    # Open file
    with open(fileName, 'r') as file:
        # Read file
        lines = (line.rstrip() for line in file)
        lines = list(line for line in lines if line) # Non-blank lines in a list
        # Get number of points
        nPoints = int(lines[0])
        # Get points
        points = []
        for i in range(nPoints):
            if i =="(" or ")":
                i = i+1
            lineS = re.sub('[()]', '', lines[i+1])
            # Get point
            point = lineS.split()
            # Convert point to float
            point = [float(point[0]), float(point[1]), float(point[2])]
            # Append point to points list
            points.append(point)
    file.close()
    return nPoints, points

# Function of get distance from center
def getDistanceFromCenter(center, point):
    # Get distance from center
    dist = np.linalg.norm(center - point)
    return dist

def getVelocityComponentsParabolic(vel, faceNormalVectors, dist, radius):
    # Get velocity x, y and z components
    velX = vel * faceNormalVectors[0] * (1 - (dist/radius)**2)
    velY = vel * faceNormalVectors[1] * (1 - (dist/radius)**2)
    velZ = vel * faceNormalVectors[2] * (1 - (dist/radius)**2)
    return velX, velY, velZ

# Function to write openfoam data format of each time parablilc velocity profile from velocity x, y and z components and distance from center
def writeOpenFoamDataFormatParabolic(fileName, nPoints, velXarray, velYarray, velZarray):
    # Open file
    with open(fileName, 'w') as file:
        # Write header
        file.write(nPoints +'\n')
        file.write('(\n')
        for i in range(int(nPoints)):
            velX = str(velXarray[i])
            velY = str(velYarray[i])
            velZ = str(velZarray[i])
            # Write point
            file.write('('+ ''.join(map(str, velX)) + ' ' +''.join(map(str,velY)) + ' ' +''.join(map(str,velZ)) + ')\n')
        file.write(')\n')
    file.close()
    #print('File '+fileName+' is written successfully')

# get random three points from points file
def getRandomThreePoints(nPoints, points):
    # Get random three points
    p1 = points[np.random.randint(0, nPoints)]
    p2 = points[np.random.randint(0, nPoints)]
    p3 = points[np.random.randint(0, nPoints)]
    return p1, p2, p3

# Function for writing openfoam data format of each time plug velocity profile from velocity x, y and z components
def writeOut(time, vel, BPM, nPoints, points, normalVector):
    # Note, always check the cneter of the circle and radius
    center = np.array([-0.0160264,-0.0217721,-0.0127536])
    radius = 0.00563
    # Write openfoam data format
    directory = 'InletBCs_'+str(BPM) # Directory name to save the files
    # be careful with the directory name
    parent_dir = os.getcwd()
    directory = os.path.join(parent_dir, directory)
    if not os.path.exists(directory):
        os.makedirs(directory)
    else:
        #detete all files in the directory
        files = glob.glob(directory+'/*')
        for f in files:
            os.remove(f)
    for t in time:
        velXarray = []
        velYarray = []
        velZarray = []
        for point in points:
            print(point)
            dist = getDistanceFromCenter(center, point)
            if dist <= radius:
                velocityMagnitude = vel[np.where(time == t)]
                # Get velocity x, y and z components
                velX, velY, velZ = getVelocityComponentsParabolic(velocityMagnitude, normalVector, dist, radius)
                velX = velX.tolist()
                velY = velY.tolist()
                velZ = velZ.tolist()
                velXarray.append(velX[0])
                velYarray.append(velY[0])
                velZarray.append(velZ[0])
            elif dist > radius:
                velXarray.append(float(0))
                velYarray.append(float(0))
                velZarray.append(float(0))
        # Write openfoam data format
        writeOpenFoamDataFormatParabolic(os.path.join(directory,('U_'+str(format(t,'.6f')))), str(nPoints), velXarray, velYarray, velZarray)

#BPM = [50,60,70,80,90,95,100,105,110,115,120,125,130,140,150,160,170,180,190,200]
BPM = [100,120]
for i in BPM:
    # Read csv file
    times, velocity = readCSVFile('BPM'+str(i)+'.csv')
    # Read points file
    nPoints, points = readPointsFile('points')
    # Get random three points
    p1, p2, p3 = getRandomThreePoints(nPoints, points)
    # Get normal vector and make sure it faces out
    normalVector = getFaceNormalVectors(np.asarray(p1),np.asarray(p2),np.asarray(p3), 'out')
    # Write openfoam data format
    writeOut(times, velocity, i, nPoints, points, normalVector)


import numpy as np
import time 

from scipy import optimize
import scipy.signal as signal

from .nxrefine import NXRefine
from .nxreduce import NXReduce

def print_peak(input_entry,index):
    print(np.around(np.array([input_entry.peaks_inferred.x[index].nxdata,input_entry.peaks_inferred.y[index].nxdata,input_entry.peaks_inferred.z[index].nxdata]),decimals=3))
    print(input_entry.peaks_inferred.H[index],input_entry.peaks_inferred.K[index],input_entry.peaks_inferred.L[index])
    print(input_entry.peaks_inferred.pixel_count[index],input_entry.peaks_inferred.frame_intensity[index],input_entry.peaks_inferred.radius[index])

def get_xyz_mask(input_entry,h,k,l,verbose=False):

    detector_info=NXRefine(input_entry)

    chi=detector_info.chi*np.pi/180.
    omega=detector_info.omega*np.pi/180.
    gonpitch=detector_info.gonpitch*np.pi/180.

    chi_mat=np.array([[1,0,0],[0,np.cos(chi),-np.sin(chi)],[0,np.sin(chi),np.cos(chi)]])
    omega_mat=np.array([[np.cos(omega),-np.sin(omega),0],[np.sin(omega),np.cos(omega),0],[0,0,1]])
    gonpitch_mat=np.array([[np.cos(gonpitch),0,np.sin(gonpitch)],[0,1,0],[-np.sin(gonpitch),0,np.cos(gonpitch)]])

    v7=np.array([[h],[k],[l]])

    v6=np.dot(np.asarray(detector_info.Bmat),v7)

    v5=np.dot(np.asarray(detector_info.Umat),v6)

    Gmat_0=np.dot(gonpitch_mat,np.dot(omega_mat,chi_mat))

    t_E=np.asarray(detector_info.Evec)

    t_ds=np.asarray(detector_info.Dvec)

    def ewald_cond(phi):
        phi=phi*np.pi/180.
        func=t_E[0,0]**2-((Gmat_0[0,0]*v5[0,0]+Gmat_0[0,1]*v5[1,0])*np.cos(phi)+(Gmat_0[0,1]*v5[0,0]-Gmat_0[0,0]*v5[1,0])*np.sin(phi)+Gmat_0[0,2]*v5[2,0]+t_E[0,0])**2-((Gmat_0[1,0]*v5[0,0]+Gmat_0[1,1]*v5[1,0])*np.cos(phi)+(Gmat_0[1,1]*v5[0,0]-Gmat_0[1,0]*v5[1,0])*np.sin(phi)+Gmat_0[1,2]*v5[2,0])**2-((Gmat_0[2,0]*v5[0,0]+Gmat_0[2,1]*v5[1,0])*np.cos(phi)+(Gmat_0[2,1]*v5[0,0]-Gmat_0[2,0]*v5[1,0])*np.sin(phi)+Gmat_0[2,2]*v5[2,0])**2
        return func

    def get_ij(v5,phi):
        Gmat_phi=detector_info.Gmat(phi)
        v4=np.dot(Gmat_phi,v5)
        p=(v4+t_E)/np.linalg.norm(v4+t_E)
        v3=(-t_ds[0,0]/p[0,0])*p
        v2=np.dot(np.asarray(detector_info.Dmat),(v3+t_ds))
        v1=1./0.172*np.dot(np.asarray(detector_info.Omat),v2)+np.asarray(detector_info.Cvec)
        return v1[0,0],v1[1,0]
    if(h==0 and k==0 and l==0):
        peaks_detector=np.zeros((0,3),dtype='float')
    elif(optimize.fsolve(ewald_cond,45,full_output=1)[2]==1):
        
        phi_solutions=np.unique(np.around(np.array([    optimize.fsolve(ewald_cond,15)%360,
            optimize.fsolve(ewald_cond,45)%360,
            optimize.fsolve(ewald_cond,75)%360,
            optimize.fsolve(ewald_cond,105)%360,
            optimize.fsolve(ewald_cond,135)%360,
            optimize.fsolve(ewald_cond,165)%360,
            optimize.fsolve(ewald_cond,195)%360,
            optimize.fsolve(ewald_cond,225)%360,
            optimize.fsolve(ewald_cond,255)%360,
            optimize.fsolve(ewald_cond,285)%360,
            optimize.fsolve(ewald_cond,315)%360,
            optimize.fsolve(ewald_cond,345)%360,
            optimize.fsolve(ewald_cond,375)%360,
            ]),decimals=4))
        #print(phi_solutions)
        peaks_detector=np.zeros((len(phi_solutions),3))
        
        for i in range(0,len(phi_solutions)):
            x,y=get_ij(v5,phi_solutions[i])
            z=((phi_solutions[i]-detector_info.phi_start)*10)%3600
            if z<25:
                z=z+3600
            peaks_detector[i,:]=np.array([x,y,z])
    else:
        peaks_detector=np.zeros((0,3),dtype='float')
    if verbose==True:
        print('Check 1:',peaks_detector)
#####discard solutions that are not on the detector
    peaks_detector = peaks_detector[np.logical_not(np.logical_or(peaks_detector[:,0] > 1474, peaks_detector[:,0] < 1))]
    peaks_detector = peaks_detector[np.logical_not(np.logical_or(peaks_detector[:,1] > 1678, peaks_detector[:,1] < 1))]
    if verbose==True:
        print('Check 2:',peaks_detector)
########attempt to realign any peaks with the first moment about z with a linear correction
    for i in range(0,len(peaks_detector[:,0])):
        xmin=np.int(peaks_detector[i,0]-30)
        xmax=np.int(peaks_detector[i,0]+31)
        ymin=np.int(peaks_detector[i,1]-30)
        ymax=np.int(peaks_detector[i,1]+31)
        zmin=np.int(peaks_detector[i,2]-10)
        zmax=np.int(peaks_detector[i,2]+11)
        if xmin<0:
            xmin=0
        if xmax>1476:
            xmax=1476
        if ymin<0:
            ymin=0
        if ymax>1680:
            ymax=1680
        if zmin<0:
            zmin=0
        if zmax>3650:
            zmax=3650
        zframes=input_entry.data.frame_number[zmin:zmax].nxdata
        zvals=input_entry.data.data[zmin:zmax,ymin:ymax,xmin:xmax].sum(1).sum(1)
        try:
            slope=(zvals[::-1][0]-zvals[0])/(zframes[::-1][0]-zframes[0])
            constant=zvals[0]-slope*zframes[0]
            zlin=zframes*slope+constant
            z_mom=(zframes*(zvals-zlin)).sum(0)/(zvals-zlin).sum(0)
            if z_mom<zmax and z_mom>zmin:
                peaks_detector[i,2]=z_mom
        except ZeroDivisionError as err:
            if verbose==True:
                print('Handling run-time error:', err)
    if verbose==True:
        print('Check 3:',peaks_detector)
    peaks_detector = peaks_detector[np.logical_not(np.logical_or(peaks_detector[:,2] > 3648, peaks_detector[:,2] < 0))]
    if verbose==True:
        print('Check 4:',peaks_detector)
###### three possibilities: no solutions, one solution on detector, or two solutions on detector (add error check for more solutions?)
    if(peaks_detector.shape[0]==0):
        return peaks_detector.astype('float')
    elif(peaks_detector.shape[0]==1):
        if peaks_detector[0,2]<48:
            peaks_detector=np.vstack((peaks_detector,peaks_detector[0,:]+np.array([0,0,3600])))
        if peaks_detector[0,2]>3600:
            peaks_detector=np.vstack((peaks_detector,peaks_detector[0,:]-np.array([0,0,3600])))
        return peaks_detector.astype('float')
    else:
        if peaks_detector[0,2]<48:
            peaks_detector=np.vstack((peaks_detector,peaks_detector[0,:]+np.array([0,0,3600])))
        if peaks_detector[0,2]>3600:
            peaks_detector=np.vstack((peaks_detector,peaks_detector[0,:]-np.array([0,0,3600])))
        if peaks_detector[1,2]<48:
            peaks_detector=np.vstack((peaks_detector,peaks_detector[1,:]+np.array([0,0,3600])))
        if peaks_detector[1,2]>3600:
            peaks_detector=np.vstack((peaks_detector,peaks_detector[1,:]-np.array([0,0,3600])))
        return peaks_detector.astype('float')

def generate_xyz_peak_list(input_entry,hmin,hmax,kmin,kmax,lmin,lmax,verbose=False):
    xyz_array=np.zeros((1,9))
    for l in np.arange(lmin,lmax+1):
        for k in np.arange(kmin,kmax+1):
            for h in np.arange(hmin,hmax+1):
                if verbose==True:
                    print(h,k,l)
                peak_xyz=get_xyz_mask(input_entry,h,k,l)
                if len(peak_xyz[:,0])<1:
                    continue
                for i in range(0,len(peak_xyz[:,0])):
                    xmin=(np.int(np.rint(peak_xyz[i,0]))-10)
                    xmax=(np.int(np.rint(peak_xyz[i,0]))+11)
                    ymin=(np.int(np.rint(peak_xyz[i,1]))-10)
                    ymax=(np.int(np.rint(peak_xyz[i,1]))+11)
                    if xmin<0:
                        xmin=0
                    if ymin<0:
                        ymin=0
                    zframe=np.int(np.rint(peak_xyz[i,2]))
                    frame_intensity=(input_entry.data.data[zframe,ymin:ymax,xmin:xmax].sum().nxdata+len(np.where(input_entry.data.data[zframe,ymin:ymax,xmin:xmax].nxdata==-1)[0]))*21.*21./(1.*len(np.where(input_entry.data.data[zframe,ymin:ymax,xmin:xmax].nxdata>-1)[0]))
                    mask_radius=frame_mask_size(frame_intensity)
                    xyz_entry=np.array([[peak_xyz[i,0],peak_xyz[i,1],peak_xyz[i,2],input_entry.data.data[zframe,np.int(np.rint(peak_xyz[i,1])),np.int(np.rint(peak_xyz[i,0]))].nxdata,h,k,l,
                        frame_intensity,mask_radius]])
                    xyz_array=np.concatenate((xyz_array,xyz_entry),axis=0)
    xyz_array=np.delete(xyz_array,0,0)        
    return xyz_array.astype('float')

def write_inferred_peaks(input_entry,xyz_array):
    input_entry.peaks_inferred=NXdata()
    input_entry.peaks_inferred.x=NXfield(xyz_array[:,0],name='x')
    input_entry.peaks_inferred.y=NXfield(xyz_array[:,1],name='y')
    input_entry.peaks_inferred.z=NXfield(xyz_array[:,2],name='z')
    input_entry.peaks_inferred.pixel_count=NXfield(xyz_array[:,3],name='pixel_count')
    input_entry.peaks_inferred.frame_intensity=NXfield(xyz_array[:,7],name='frame_intensity')
    input_entry.peaks_inferred.H=NXfield(xyz_array[:,4],name='H')
    input_entry.peaks_inferred.K=NXfield(xyz_array[:,5],name='K')
    input_entry.peaks_inferred.L=NXfield(xyz_array[:,6],name='L')
    input_entry.peaks_inferred.radius=NXfield(xyz_array[:,8],name='radius')
    #input_entry.mask_xyz.width=NXfield(xyz_array[:,9],name='width')

def mask_xyz_array(input_entry,xyz_array):
    input_entry.mask_xyz=NXdata()
    input_entry.mask_xyz.x=NXfield(xyz_array[:,0],name='x')
    input_entry.mask_xyz.y=NXfield(xyz_array[:,1],name='y')
    input_entry.mask_xyz.z=NXfield(xyz_array[:,2],name='z')
    input_entry.mask_xyz.radius=NXfield(xyz_array[:,3],name='radius')

def frame_mask_size(frame_intensity,find_zero=False):
    a=1.3858
    b=0.330556764635949
    c=-134.21+40#radius_add
    if find_zero==True:
        return np.real(-(c/a)**(1./b))
    else:
        if(frame_intensity<1):
            return np.int(0.0)
        else:
            radius=np.real(c+a*(frame_intensity**b))
            return np.int(radius)

def get_hkl_element(input_array,h,k,l):
    xyz_array=np.zeros((0,9))
    elements=np.intersect1d(np.where(input_array[:,4]==h)[0],np.intersect1d(np.where(input_array[:,5]==k)[0],np.intersect1d(np.where(input_array[:,6]==l)[0],np.where(input_array[:,3]>-10000)[0])))
    for i in range(0,len(elements)):
        xyz_array=np.concatenate((xyz_array,input_array[elements[i:i+1]]),axis=0)
    return xyz_array

def determine_mask_frames(input_entry,xval,yval,zval):
    x=np.int(np.rint(xval))
    y=np.int(np.rint(yval))
    z=np.int(np.rint(zval))
    index_list=np.arange(-20,21)
    if z<20:
        index_list=np.arange(0-z,21)
    if z>3628:
        index_list=np.arange(-20,(3649-z))
    xmin=(np.int(np.rint(x-10)))
    xmax=(np.int(np.rint(x+11)))
    ymin=(np.int(np.rint(y-10)))
    ymax=(np.int(np.rint(y+11)))
    if xmin<0:
        xmin=0
    if ymin<0:
        ymin=0    
    intensity_list=input_entry.data.data[z+index_list[0]:z+index_list[-1]+1,ymin:ymax,xmin:xmax].sum(1).sum(1).nxdata*21.*21./(1.*len(np.where(input_entry.data.data[z,ymin:ymax,xmin:xmax].nxdata>-1)[0]))
    mask_coords=np.zeros((0,4),dtype='int')
    frame_threshold=frame_mask_size(0.0,find_zero=True)
    mask_frames=(np.where(intensity_list>frame_threshold)[0]).astype('int')######fix this limit!
    for i in range(0,len(mask_frames)):
        new_coords=np.array([[x,y,z+index_list[mask_frames[i]],frame_mask_size(intensity_list[mask_frames[i]])]])
        mask_coords=np.concatenate((mask_coords,new_coords),axis=0)
    mask_coords = mask_coords[np.logical_not(mask_coords[:,3]<1)]
    return mask_coords

def make_peaks_inferred_array(input_entry):
    peaks_inferred_array=np.stack((input_entry.peaks_inferred.x.nxdata,
        input_entry.peaks_inferred.y.nxdata,
        input_entry.peaks_inferred.z.nxdata,
        input_entry.peaks_inferred.pixel_count.nxdata,
        input_entry.peaks_inferred.H.nxdata,
        input_entry.peaks_inferred.K.nxdata,
        input_entry.peaks_inferred.L.nxdata,
        input_entry.peaks_inferred.frame_intensity.nxdata,
        input_entry.peaks_inferred.radius.nxdata,
        ),axis=1)
    return peaks_inferred_array

def make_mask_xyz_array(input_entry):
    peaks_inferred_array=np.stack((input_entry.mask_xyz.x.nxdata,
        input_entry.mask_xyz.y.nxdata,
        input_entry.mask_xyz.z.nxdata,
        input_entry.mask_xyz.radius.nxdata,
        ),axis=1)
    return peaks_inferred_array

def make_mask_array(input_root):
    f1_array=make_peaks_inferred_array(input_root.f1)
    f2_array=make_peaks_inferred_array(input_root.f2)
    f3_array=make_peaks_inferred_array(input_root.f3)
    xyz_array=np.zeros((0,4))
    for i in range(0,len(f1_array[:,0])):
        xval=f1_array[i,0]
        yval=f1_array[i,1]
        zval=f1_array[i,2]
        if zval<0:
            continue
        if f1_array[i,3]>0:
            xyz_array=np.concatenate((xyz_array,determine_mask_frames(input_root.f1,xval,yval,zval)),axis=0)
        elif f1_array[i,3]<0:
            hval=f1_array[i,4]
            kval=f1_array[i,5]
            lval=f1_array[i,6]
            radius=0
            width=0
            checka=get_hkl_element(f2_array,hval,kval,lval)
            checka=checka[np.logical_not(checka[:,3]<0)]
            for i in range(0,checka.shape[0]):
                check_mask=determine_mask_frames(input_root.f2,checka[i,0],checka[i,1],checka[i,2])
                if(check_mask.shape[0]>0):
                    if(np.amax(check_mask[:,3])>radius):
                        radius=np.amax(check_mask[:,3])
                    if(check_mask.shape[0]>width):
                        width=check_mask.shape[0]
            checkb=get_hkl_element(f3_array,hval,kval,lval)
            checkb=checkb[np.logical_not(checkb[:,3]<0)]
            for i in range(0,checkb.shape[0]):
                check_mask=determine_mask_frames(input_root.f3,checkb[i,0],checkb[i,1],checkb[i,2])
                if(check_mask.shape[0]>0):
                    if(np.amax(check_mask[:,3])>radius):
                        radius=np.amax(check_mask[:,3])
                    if(check_mask.shape[0]>width):
                        width=check_mask.shape[0]
            if(width%2==0):
                width=width+1
            width=width+2
            radius=radius+20.
            xmin=(np.int(np.rint(xval)-20))
            xmax=(np.int(np.rint(xval)+21))
            ymin=(np.int(np.rint(yval)-20))
            ymax=(np.int(np.rint(yval)+21))
            zmin=np.int(np.rint(zval)-5)
            zmax=np.int(np.rint(zval)+6)
            if xmin<0:
                xmin=0
            if ymin<0:
                ymin=0
            if zmin<0:
                zmin=0
            if zmax>3650:
                zmax=3650
            zframes=input_root.f1.data.frame_number[zmin:zmax].nxdata
            z_intensity=input_root.f1.data.data[zmin:zmax,ymin:ymax,xmin:xmax].sum(1).sum(1).nxdata
            zval=zframes[np.where(z_intensity==np.amax(z_intensity))[0][0]]
            infer_xyz=np.zeros((width,4))
            infer_xyz[:,0]=xval
            infer_xyz[:,1]=yval
            infer_xyz[:,2]=np.arange(np.rint(zval)-width//2,np.rint(zval)+width//2+1)
            infer_xyz[:,3]=radius
            if(radius>0):
                xyz_array=np.concatenate((xyz_array,infer_xyz),axis=0)
    xyz_array = xyz_array[np.logical_not(xyz_array[:,2]<0)]
    xyz_array = xyz_array[np.logical_not(xyz_array[:,2]>3649)]
    input_root.f1.mask_xyz=NXentry()
    input_root.f1.mask_xyz.x=NXfield(xyz_array[:,0],name='x')
    input_root.f1.mask_xyz.y=NXfield(xyz_array[:,1],name='y')
    input_root.f1.mask_xyz.z=NXfield(xyz_array[:,2],name='z')
    input_root.f1.mask_xyz.radius=NXfield(xyz_array[:,3],name='radius')

    xyz_array=np.zeros((0,4))
    for i in range(0,len(f2_array[:,0])):
        xval=f2_array[i,0]
        yval=f2_array[i,1]
        zval=f2_array[i,2]
        if zval<0:
            continue
        if f2_array[i,3]>0:
            xyz_array=np.concatenate((xyz_array,determine_mask_frames(input_root.f2,xval,yval,zval)),axis=0)
        elif f2_array[i,3]<0:
            hval=f2_array[i,4]
            kval=f2_array[i,5]
            lval=f2_array[i,6]
            radius=0
            width=0
            checka=get_hkl_element(f1_array,hval,kval,lval)
            checka=checka[np.logical_not(checka[:,3]<0)]
            for i in range(0,checka.shape[0]):
                check_mask=determine_mask_frames(input_root.f1,checka[i,0],checka[i,1],checka[i,2])
                if(check_mask.shape[0]>0):
                    if(np.amax(check_mask[:,3])>radius):
                        radius=np.amax(check_mask[:,3])
                    if(check_mask.shape[0]>width):
                        width=check_mask.shape[0]
            checkb=get_hkl_element(f3_array,hval,kval,lval)
            checkb=checkb[np.logical_not(checkb[:,3]<0)]
            for i in range(0,checkb.shape[0]):
                check_mask=determine_mask_frames(input_root.f3,checkb[i,0],checkb[i,1],checkb[i,2])
                if(check_mask.shape[0]>0):
                    if(np.amax(check_mask[:,3])>radius):
                        radius=np.amax(check_mask[:,3])
                    if(check_mask.shape[0]>width):
                        width=check_mask.shape[0]
            if(width%2==0):
                width=width+1
            width=width+2
            radius=radius+20.
            xmin=(np.int(np.rint(xval)-20))
            xmax=(np.int(np.rint(xval)+21))
            ymin=(np.int(np.rint(yval)-20))
            ymax=(np.int(np.rint(yval)+21))
            zmin=np.int(np.rint(zval)-5)
            zmax=np.int(np.rint(zval)+6)
            if xmin<0:
                xmin=0
            if ymin<0:
                ymin=0
            if zmin<0:
                zmin=0
            if zmax>3650:
                zmax=3650
            zframes=input_root.f2.data.frame_number[zmin:zmax].nxdata
            z_intensity=input_root.f2.data.data[zmin:zmax,ymin:ymax,xmin:xmax].sum(1).sum(1).nxdata
            zval=zframes[np.where(z_intensity==np.amax(z_intensity))[0][0]]
            infer_xyz=np.zeros((width,4))
            infer_xyz[:,0]=xval
            infer_xyz[:,1]=yval
            infer_xyz[:,2]=np.arange(np.rint(zval)-width//2,np.rint(zval)+width//2+1)
            infer_xyz[:,3]=radius
            if(radius>0):
                xyz_array=np.concatenate((xyz_array,infer_xyz),axis=0)
    xyz_array = xyz_array[np.logical_not(xyz_array[:,2]<0)]
    xyz_array = xyz_array[np.logical_not(xyz_array[:,2]>3649)]
    input_root.f2.mask_xyz=NXentry()
    input_root.f2.mask_xyz.x=NXfield(xyz_array[:,0],name='x')
    input_root.f2.mask_xyz.y=NXfield(xyz_array[:,1],name='y')
    input_root.f2.mask_xyz.z=NXfield(xyz_array[:,2],name='z')
    input_root.f2.mask_xyz.radius=NXfield(xyz_array[:,3],name='radius')

    xyz_array=np.zeros((0,4))
    for i in range(0,len(f3_array[:,0])):
        xval=f3_array[i,0]
        yval=f3_array[i,1]
        zval=f3_array[i,2]
        if zval<0:
            continue
        if f3_array[i,3]>0:
            xyz_array=np.concatenate((xyz_array,determine_mask_frames(input_root.f3,xval,yval,zval)),axis=0)
        elif f3_array[i,3]<0:
            hval=f3_array[i,4]
            kval=f3_array[i,5]
            lval=f3_array[i,6]
            radius=0
            width=0
            checka=get_hkl_element(f1_array,hval,kval,lval)
            checka=checka[np.logical_not(checka[:,3]<0)]
            for i in range(0,checka.shape[0]):
                check_mask=determine_mask_frames(input_root.f1,checka[i,0],checka[i,1],checka[i,2])
                if(check_mask.shape[0]>0):
                    if(np.amax(check_mask[:,3])>radius):
                        radius=np.amax(check_mask[:,3])
                    if(check_mask.shape[0]>width):
                        width=check_mask.shape[0]
            checkb=get_hkl_element(f2_array,hval,kval,lval)
            checkb=checkb[np.logical_not(checkb[:,3]<0)]
            for i in range(0,checkb.shape[0]):
                check_mask=determine_mask_frames(input_root.f2,checkb[i,0],checkb[i,1],checkb[i,2])
                if(check_mask.shape[0]>0):
                    if(np.amax(check_mask[:,3])>radius):
                        radius=np.amax(check_mask[:,3])
                    if(check_mask.shape[0]>width):
                        width=check_mask.shape[0]
            if(width%2==0):
                width=width+1
            width=width+2
            radius=radius+20.
            xmin=(np.int(np.rint(xval)-20))
            xmax=(np.int(np.rint(xval)+21))
            ymin=(np.int(np.rint(yval)-20))
            ymax=(np.int(np.rint(yval)+21))
            zmin=np.int(np.rint(zval)-5)
            zmax=np.int(np.rint(zval)+6)
            if xmin<0:
                xmin=0
            if ymin<0:
                ymin=0
            if zmin<0:
                zmin=0
            if zmax>3650:
                zmax=3650
            zframes=input_root.f3.data.frame_number[zmin:zmax].nxdata
            z_intensity=input_root.f3.data.data[zmin:zmax,ymin:ymax,xmin:xmax].sum(1).sum(1).nxdata
            zval=zframes[np.where(z_intensity==np.amax(z_intensity))[0][0]]
            infer_xyz=np.zeros((width,4))
            infer_xyz[:,0]=xval
            infer_xyz[:,1]=yval
            infer_xyz[:,2]=np.arange(np.rint(zval)-width//2,np.rint(zval)+width//2+1)
            infer_xyz[:,3]=radius
            if(radius>0):
                xyz_array=np.concatenate((xyz_array,infer_xyz),axis=0)
    xyz_array = xyz_array[np.logical_not(xyz_array[:,2]<0)]
    xyz_array = xyz_array[np.logical_not(xyz_array[:,2]>3649)]
    input_root.f3.mask_xyz=NXentry()
    input_root.f3.mask_xyz.x=NXfield(xyz_array[:,0],name='x')
    input_root.f3.mask_xyz.y=NXfield(xyz_array[:,1],name='y')
    input_root.f3.mask_xyz.z=NXfield(xyz_array[:,2],name='z')
    input_root.f3.mask_xyz.radius=NXfield(xyz_array[:,3],name='radius')

def mask_scan(input_root,mask_edges=True,print_time=False):
    hmin=np.rint(input_root.f1.transform.Qh[0].nxdata).astype('int')
    hmax=np.rint(input_root.f1.transform.Qh[-1].nxdata).astype('int')
    kmin=np.rint(input_root.f1.transform.Qk[0].nxdata).astype('int')
    kmax=np.rint(input_root.f1.transform.Qk[-1].nxdata).astype('int')
    lmin=np.rint(input_root.f1.transform.Ql[0].nxdata).astype('int')
    lmax=np.rint(input_root.f1.transform.Ql[-1].nxdata).astype('int')
    if print_time==True:
        f1_start=time.time()
    write_inferred_peaks(input_root.f1,generate_xyz_peak_list(input_root.f1,hmin,hmax,kmin,kmax,lmin,lmax))
    if print_time==True:
        f2_start=time.time()
    write_inferred_peaks(input_root.f2,generate_xyz_peak_list(input_root.f2,hmin,hmax,kmin,kmax,lmin,lmax))
    if print_time==True:
        f3_start=time.time()
    write_inferred_peaks(input_root.f3,generate_xyz_peak_list(input_root.f3,hmin,hmax,kmin,kmax,lmin,lmax))
    if print_time==True:
        peaks_end=time.time()    
    make_mask_array(input_root)
    if print_time==True:
        mask_xyz_end=time.time()    
    if mask_edges==True:
        add_edge_xyz(input_root.f1)
        add_edge_xyz(input_root.f2)
        add_edge_xyz(input_root.f3)
    if print_time==True:
        mask_edge_end=time.time()    
        print(str(f2_start-f1_start)+' seconds for f1 peaks')
        print(str(f3_start-f2_start)+' seconds for f2 peaks')
        print(str(peaks_end-f3_start)+' seconds for f3 peaks')
        print(str(mask_xyz_end-peaks_end)+' seconds for determining mask_xyz for all entries')
        print(str(mask_edge_end-mask_xyz_end)+' seconds for edges')
        print()
        print(str(mask_edge_end-f1_start)+' seconds total')

###################################################################################################
#additional routines to mask edges
###################################################################################################

def edge_mask(plane,intensity_factor=0.99,intensity_constant=0.0,window_size=5,horiz_size_1=10,horiz_threshold_1=0.8,vertical_size=70,vertical_threshold=0.95,
    horiz_size_2=501,horiz_threshold_2=0.3):

    overlap_size=overlap_size=window_size-1
    kern=np.ones((window_size, 1))
    kern /= kern.sum()

    horiz_kern_1=np.ones((1,horiz_size_1))
    horiz_kern_1 /= horiz_kern_1.sum()

    vertical_kern=np.ones((vertical_size, 1))
    vertical_kern /= vertical_kern.sum()

    horiz_kern_2=np.ones((1,horiz_size_2))
    horiz_kern_2 /= horiz_kern_2.sum()

    plane=np.concatenate((plane[3600-overlap_size:3600,:],plane,plane[0:overlap_size]),axis=0)
    plane[plane<0]=1
    plane_smoothed=signal.convolve(plane,kern,mode='same')
    plane_mask=plane[overlap_size:3650+overlap_size,:]-plane_smoothed[(overlap_size)//2:3650+(overlap_size)//2,:]*intensity_factor+intensity_constant
    plane_mask[plane_mask<0]=0
    plane_mask[plane_mask>0]=1

    plane_mask=signal.convolve(plane_mask,horiz_kern_1,mode='same')
    plane_mask[plane_mask<=horiz_threshold_1]=0
    plane_mask[plane_mask>horiz_threshold_1]=1
    vertical_filter=signal.convolve(plane_mask,vertical_kern,mode='same')
    vertical_filter[vertical_filter<=vertical_threshold]=0
    vertical_filter[vertical_filter>vertical_threshold]=1
    plane_mask=plane_mask-vertical_filter
    plane_mask=signal.convolve(plane_mask,horiz_kern_2,mode='same')
    plane_mask[plane_mask<=horiz_threshold_2]=0
    plane_mask[plane_mask>horiz_threshold_2]=1

    return plane_mask

def plane_steps(plane):
    length=plane.shape[1]
    plane_diff=plane[:,0:length-1].astype('int')-plane[:,1:length].astype('int')
    return plane_diff

def mask_frame_row(row,frame_number,verbose=False):
    axis_max=row.shape[0]
    circ_array=np.zeros((0,3))
    neg1=np.where(row==-1)[0]
    pos1=np.where(row==1)[0]
    if row.sum() in np.array([-1,0,1]):
        if neg1.shape[0]==0 and pos1.shape[0]==0:
            if verbose==True:
                print('Using Method 1')
            return circ_array
        elif neg1.shape[0]==0 and pos1.shape[0]==1:
            if verbose==True:
                print('Using Method 2')
            infer_circ=np.array([[pos1[0]/2,frame_number,pos1[0]/2]])
            circ_array=np.concatenate((circ_array,infer_circ),axis=0)
            return circ_array
        elif neg1.shape[0]==1 and pos1.shape[0]==0:
            if verbose==True:
                print('Using Method 3')
            infer_circ=np.array([[(neg1[0]+axis_max)/2,frame_number,(axis_max-neg1[0])/2]])
            circ_array=np.concatenate((circ_array,infer_circ),axis=0)
            return circ_array
        elif neg1.shape[0]==1 and pos1.shape[0]==1 and pos1[0]<neg1[0]:
            if verbose==True:
                print('Using Method 4')
            infer_circ=np.array([[pos1[0]/2,frame_number,pos1[0]/2]])
            circ_array=np.concatenate((circ_array,infer_circ),axis=0)
            infer_circ=np.array([[(neg1[0]+axis_max)/2,frame_number,(axis_max-neg1[0])/2]])
            circ_array=np.concatenate((circ_array,infer_circ),axis=0)
            return circ_array
        elif neg1.shape[0]==1 and pos1.shape[0]==1 and pos1[0]>neg1[0]:
            if verbose==True:
                print('Using Method 4a')
            infer_circ=np.array([[(neg1[0]+pos1[0])/2,frame_number,(pos1[0]-neg1[0])/2]])
            circ_array=np.concatenate((circ_array,infer_circ),axis=0)
            return circ_array
        elif neg1.shape[0]>pos1.shape[0]:
            if verbose==True:
                print('Using Method 5')
            for i in range(0,pos1.shape[0]):
                infer_circ=np.array([[(neg1[i]+pos1[i])/2,frame_number,(pos1[i]-neg1[i])/2]])
                circ_array=np.concatenate((circ_array,infer_circ),axis=0)
            infer_circ=np.array([[(neg1[::-1][0]+axis_max)/2,frame_number,(axis_max-neg1[::-1][0])/2]])
            circ_array=np.concatenate((circ_array,infer_circ),axis=0)
            return circ_array
        elif neg1.shape[0]<pos1.shape[0]:
            if verbose==True:
                print('Using Method 6')
            for i in range(0,neg1.shape[0]):
                infer_circ=np.array([[(neg1[i]+pos1[i+1])/2,frame_number,(pos1[i+1]-neg1[i])/2]])
                circ_array=np.concatenate((circ_array,infer_circ),axis=0)
            infer_circ=np.array([[pos1[0]/2,frame_number,pos1[0]/2]])
            circ_array=np.concatenate((circ_array,infer_circ),axis=0)
            return circ_array
        elif neg1.shape[0]==pos1.shape[0] and pos1[0]>neg1[0]:
            if verbose==True:
                print('Using Method 7')
            for i in range(0,neg1.shape[0]):
                infer_circ=np.array([[(neg1[i]+pos1[i])/2,frame_number,(pos1[i]-neg1[i])/2]])
                circ_array=np.concatenate((circ_array,infer_circ),axis=0)
            return circ_array
        elif neg1.shape[0]==pos1.shape[0] and pos1[0]<neg1[0]:
            if verbose==True:
                print('Using Method 8')
            for i in range(0,neg1.shape[0]-1):
                infer_circ=np.array([[(neg1[i]+pos1[i+1])/2,frame_number,(pos1[i+1]-neg1[i])/2]])
                circ_array=np.concatenate((circ_array,infer_circ),axis=0)
            infer_circ=np.array([[pos1[0]/2,frame_number,pos1[0]/2]])
            circ_array=np.concatenate((circ_array,infer_circ),axis=0)
            infer_circ=np.array([[(neg1[::-1][0]+axis_max)/2,frame_number,(axis_max-neg1[::-1][0])/2]])
            circ_array=np.concatenate((circ_array,infer_circ),axis=0)
            return circ_array

def mask_edges(input_entry):
    x_pixel_max=input_entry.data.x_pixel.shape[0]-1
    y_pixel_max=input_entry.data.y_pixel.shape[0]-1
    number_of_frames=input_entry.data.frame_number.shape[0]
    x_min_plane=input_entry.data.data[:,:,0].nxdata
    x_max_plane=input_entry.data.data[:,:,x_pixel_max].nxdata
    y_min_plane=input_entry.data.data[:,0,:].nxdata
    y_max_plane=input_entry.data.data[:,y_pixel_max,:].nxdata

    x_min_plane_mask=np.logical_or(edge_mask(x_min_plane,intensity_factor=0.99,intensity_constant=0.0,window_size=3,horiz_size_1=10,horiz_threshold_1=0.8,vertical_size=70,vertical_threshold=0.95,
    horiz_size_2=501,horiz_threshold_2=0.3),edge_mask(x_min_plane,intensity_factor=1.5,intensity_constant=0.0,window_size=1001,horiz_size_1=10,horiz_threshold_1=0.8,vertical_size=70,vertical_threshold=0.95,
    horiz_size_2=501,horiz_threshold_2=0.3))

    x_max_plane_mask=np.logical_or(edge_mask(x_max_plane,intensity_factor=0.99,intensity_constant=0.0,window_size=3,horiz_size_1=10,horiz_threshold_1=0.8,vertical_size=70,vertical_threshold=0.95,
    horiz_size_2=501,horiz_threshold_2=0.3),edge_mask(x_max_plane,intensity_factor=1.5,intensity_constant=0.0,window_size=1001,horiz_size_1=10,horiz_threshold_1=0.8,vertical_size=70,vertical_threshold=0.95,
    horiz_size_2=501,horiz_threshold_2=0.3))

    y_min_plane_mask=np.logical_or(edge_mask(y_min_plane,intensity_factor=0.99,intensity_constant=0.0,window_size=3,horiz_size_1=10,horiz_threshold_1=0.8,vertical_size=70,vertical_threshold=0.95,
    horiz_size_2=501,horiz_threshold_2=0.3),edge_mask(y_min_plane,intensity_factor=1.5,intensity_constant=0.0,window_size=1001,horiz_size_1=10,horiz_threshold_1=0.8,vertical_size=70,vertical_threshold=0.95,
    horiz_size_2=501,horiz_threshold_2=0.3))

    y_max_plane_mask=np.logical_or(edge_mask(y_max_plane,intensity_factor=0.99,intensity_constant=0.0,window_size=3,horiz_size_1=10,horiz_threshold_1=0.8,vertical_size=70,vertical_threshold=0.95,
    horiz_size_2=501,horiz_threshold_2=0.3),edge_mask(y_max_plane,intensity_factor=1.5,intensity_constant=0.0,window_size=1001,horiz_size_1=10,horiz_threshold_1=0.8,vertical_size=70,vertical_threshold=0.95,
    horiz_size_2=501,horiz_threshold_2=0.3))

    x_min_plane_steps=plane_steps(x_min_plane_mask)
    x_max_plane_steps=plane_steps(x_max_plane_mask)
    y_min_plane_steps=plane_steps(y_min_plane_mask)
    y_max_plane_steps=plane_steps(y_max_plane_mask)

    x_min_circ=np.zeros((0,3))
    x_max_circ=np.zeros((0,3))
    y_min_circ=np.zeros((0,3))
    y_max_circ=np.zeros((0,3))

    for i in range(0,number_of_frames):
        x_min_circ=np.concatenate((x_min_circ,mask_frame_row(x_min_plane_steps[i],i,verbose=False)),axis=0)
    
    for i in range(0,number_of_frames):
        x_max_circ=np.concatenate((x_max_circ,mask_frame_row(x_max_plane_steps[i],i,verbose=False)),axis=0)

    for i in range(0,number_of_frames):
        y_min_circ=np.concatenate((y_min_circ,mask_frame_row(y_min_plane_steps[i],i,verbose=False)),axis=0)
    
    for i in range(0,number_of_frames):
        y_max_circ=np.concatenate((y_max_circ,mask_frame_row(y_max_plane_steps[i],i,verbose=False)),axis=0)

    x_min_xyz=np.zeros((x_min_circ.shape[0],4))
    x_min_xyz[:,1:4]=x_min_circ[:,:]

    x_max_xyz=x_pixel_max*np.ones((x_max_circ.shape[0],4))
    x_max_xyz[:,1:4]=x_max_circ[:,:]

    y_min_xyz=np.zeros((y_min_circ.shape[0],4))
    y_min_xyz[:,0]=y_min_circ[:,0]
    y_min_xyz[:,2:4]=y_min_circ[:,1:3]

    y_max_xyz=y_pixel_max*np.ones((y_max_circ.shape[0],4))
    y_max_xyz[:,0]=y_max_circ[:,0]
    y_max_xyz[:,2:4]=y_max_circ[:,1:3]

    return np.concatenate((x_min_xyz,x_max_xyz,y_min_xyz,y_max_xyz),axis=0)

def add_edge_xyz(input_entry):
    mask_xyz_volume=make_mask_xyz_array(input_entry)
    xyz_array=np.concatenate((mask_xyz_volume,mask_edges(input_entry)),axis=0)
    #del input_entry.mask_xyz
    #input_entry.mask_xyz=NXentry()
    del input_entry['mask_xyz']['x']
    del input_entry['mask_xyz']['y']
    del input_entry['mask_xyz']['z']
    del input_entry['mask_xyz']['radius']
    input_entry.mask_xyz.x=NXfield(xyz_array[:,0],name='x')
    input_entry.mask_xyz.y=NXfield(xyz_array[:,1],name='y')
    input_entry.mask_xyz.z=NXfield(xyz_array[:,2],name='z')
    input_entry.mask_xyz.radius=NXfield(xyz_array[:,3],name='radius')

##############################################

def add_mask_xyz_edges(input_root):
    fx_mask_xyz_edges_array=mask_edges(input_root['f1'])
    fx_reduce=NXReduce(input_root['f1'])
    entry=fx_reduce.mask_root['entry']
    if 'mask_xyz_edges' in entry:
        del entry['mask_xyz_edges']
    entry['mask_xyz_edges']=NXcollection()
    entry['mask_xyz_edges']['x']=fx_mask_xyz_edges_array[:,0]
    entry['mask_xyz_edges']['y']=fx_mask_xyz_edges_array[:,1]
    entry['mask_xyz_edges']['z']=fx_mask_xyz_edges_array[:,2]
    entry['mask_xyz_edges']['radius']=fx_mask_xyz_edges_array[:,3]
    entry['mask_xyz_edges']['H']=np.zeros(fx_mask_xyz_edges_array[:,0].shape[0])
    entry['mask_xyz_edges']['K']=np.zeros(fx_mask_xyz_edges_array[:,0].shape[0])
    entry['mask_xyz_edges']['L']=np.zeros(fx_mask_xyz_edges_array[:,0].shape[0])
    entry['mask_xyz_edges']['pixel_count']=np.zeros(fx_mask_xyz_edges_array[:,0].shape[0])
    fx_reduce.write_mask(fx_reduce.read_peaks('mask_xyz_edges'))

    fx_mask_xyz_edges_array=mask_edges(input_root['f2'])
    fx_reduce=NXReduce(input_root['f2'])
    entry=fx_reduce.mask_root['entry']
    if 'mask_xyz_edges' in entry:
        del entry['mask_xyz_edges']
    entry['mask_xyz_edges']=NXcollection()
    entry['mask_xyz_edges']['x']=fx_mask_xyz_edges_array[:,0]
    entry['mask_xyz_edges']['y']=fx_mask_xyz_edges_array[:,1]
    entry['mask_xyz_edges']['z']=fx_mask_xyz_edges_array[:,2]
    entry['mask_xyz_edges']['radius']=fx_mask_xyz_edges_array[:,3]
    entry['mask_xyz_edges']['H']=np.zeros(fx_mask_xyz_edges_array[:,0].shape[0])
    entry['mask_xyz_edges']['K']=np.zeros(fx_mask_xyz_edges_array[:,0].shape[0])
    entry['mask_xyz_edges']['L']=np.zeros(fx_mask_xyz_edges_array[:,0].shape[0])
    entry['mask_xyz_edges']['pixel_count']=np.zeros(fx_mask_xyz_edges_array[:,0].shape[0])
    fx_reduce.write_mask(fx_reduce.read_peaks('mask_xyz_edges'))

    fx_mask_xyz_edges_array=mask_edges(input_root['f3'])
    fx_reduce=NXReduce(input_root['f3'])
    entry=fx_reduce.mask_root['entry']
    if 'mask_xyz_edges' in entry:
        del entry['mask_xyz_edges']
    entry['mask_xyz_edges']=NXcollection()
    entry['mask_xyz_edges']['x']=fx_mask_xyz_edges_array[:,0]
    entry['mask_xyz_edges']['y']=fx_mask_xyz_edges_array[:,1]
    entry['mask_xyz_edges']['z']=fx_mask_xyz_edges_array[:,2]
    entry['mask_xyz_edges']['radius']=fx_mask_xyz_edges_array[:,3]
    entry['mask_xyz_edges']['H']=np.zeros(fx_mask_xyz_edges_array[:,0].shape[0])
    entry['mask_xyz_edges']['K']=np.zeros(fx_mask_xyz_edges_array[:,0].shape[0])
    entry['mask_xyz_edges']['L']=np.zeros(fx_mask_xyz_edges_array[:,0].shape[0])
    entry['mask_xyz_edges']['pixel_count']=np.zeros(fx_mask_xyz_edges_array[:,0].shape[0])
    fx_reduce.write_mask(fx_reduce.read_peaks('mask_xyz_edges'))

########utility scripts

def add_mask_adhoc(input_entry,x,y,z,radius,H,K,L,pixel_count):
    fx_reduce=NXReduce(input_entry)
    entry=fx_reduce.mask_root['entry']
    if 'mask_xyz_adhoc' not in entry:
        entry['mask_xyz_adhoc']=NXcollection()
        entry['mask_xyz_adhoc']['x']=np.zeros(0)
        entry['mask_xyz_adhoc']['y']=np.zeros(0)
        entry['mask_xyz_adhoc']['z']=np.zeros(0)
        entry['mask_xyz_adhoc']['radius']=np.zeros(0)
        entry['mask_xyz_adhoc']['H']=np.zeros(0)
        entry['mask_xyz_adhoc']['K']=np.zeros(0)
        entry['mask_xyz_adhoc']['L']=np.zeros(0)
        entry['mask_xyz_adhoc']['pixel_count']=np.zeros(0)
    xcoll=np.append(entry['mask_xyz_adhoc']['x'].nxdata,x)
    ycoll=np.append(entry['mask_xyz_adhoc']['y'].nxdata,y)
    zcoll=np.append(entry['mask_xyz_adhoc']['z'].nxdata,z)
    radcoll=np.append(entry['mask_xyz_adhoc']['radius'].nxdata,radius)
    Hcoll=np.append(entry['mask_xyz_adhoc']['H'].nxdata,H)
    Kcoll=np.append(entry['mask_xyz_adhoc']['K'].nxdata,K)
    Lcoll=np.append(entry['mask_xyz_adhoc']['L'].nxdata,L)
    pixcoll=np.append(entry['mask_xyz_adhoc']['pixel_count'].nxdata,pixel_count)
    del entry['mask_xyz_adhoc']['x']
    del entry['mask_xyz_adhoc']['y']
    del entry['mask_xyz_adhoc']['z']
    del entry['mask_xyz_adhoc']['radius']
    del entry['mask_xyz_adhoc']['H']
    del entry['mask_xyz_adhoc']['K']
    del entry['mask_xyz_adhoc']['L']
    del entry['mask_xyz_adhoc']['pixel_count']
    entry['mask_xyz_adhoc']['x']=xcoll
    entry['mask_xyz_adhoc']['y']=ycoll
    entry['mask_xyz_adhoc']['z']=zcoll
    entry['mask_xyz_adhoc']['radius']=radcoll
    entry['mask_xyz_adhoc']['H']=Hcoll
    entry['mask_xyz_adhoc']['K']=Kcoll
    entry['mask_xyz_adhoc']['L']=Lcoll
    entry['mask_xyz_adhoc']['pixel_count']=pixcoll

def write_mask_adhoc(input_root):
    fx_reduce=NXReduce(input_root['f1'])
    entry=fx_reduce.mask_root['entry']
    if 'mask_xyz_adhoc' in entry:
        fx_reduce.write_mask(fx_reduce.read_peaks('mask_xyz_adhoc'))
    fx_reduce=NXReduce(input_root['f2'])
    entry=fx_reduce.mask_root['entry']
    if 'mask_xyz_adhoc' in entry:
        fx_reduce.write_mask(fx_reduce.read_peaks('mask_xyz_adhoc'))
    fx_reduce=NXReduce(input_root['f3'])
    entry=fx_reduce.mask_root['entry']
    if 'mask_xyz_adhoc' in entry:
        fx_reduce.write_mask(fx_reduce.read_peaks('mask_xyz_adhoc'))

def update_mask_xyz(input_root):
    scan_entry='f1'
    fx_reduce=NXReduce(input_root[scan_entry])
    entry=fx_reduce.mask_root['entry']
    entry['mask_xyz']=NXcollection()
    entry['mask_xyz']['x']=input_root[scan_entry]['mask_xyz']['x'].nxdata
    entry['mask_xyz']['y']=input_root[scan_entry]['mask_xyz']['y'].nxdata
    entry['mask_xyz']['z']=input_root[scan_entry]['mask_xyz']['z'].nxdata
    entry['mask_xyz']['radius']=input_root[scan_entry]['mask_xyz']['radius'].nxdata
    entry['mask_xyz']['H']=np.zeros(entry['mask_xyz']['x'].nxdata.shape[0])
    entry['mask_xyz']['K']=np.zeros(entry['mask_xyz']['x'].nxdata.shape[0])
    entry['mask_xyz']['L']=np.zeros(entry['mask_xyz']['x'].nxdata.shape[0])
    entry['mask_xyz']['pixel_count']=np.zeros(entry['mask_xyz']['x'].nxdata.shape[0])
    fx_reduce.write_mask(fx_reduce.read_peaks('mask_xyz'))
    fx_reduce.link_mask()
    input_root[scan_entry]['nxprepare_mask']=NXprocess()

    scan_entry='f2'
    fx_reduce=NXReduce(input_root[scan_entry])
    entry=fx_reduce.mask_root['entry']
    entry['mask_xyz']=NXcollection()
    entry['mask_xyz']['x']=input_root[scan_entry]['mask_xyz']['x'].nxdata
    entry['mask_xyz']['y']=input_root[scan_entry]['mask_xyz']['y'].nxdata
    entry['mask_xyz']['z']=input_root[scan_entry]['mask_xyz']['z'].nxdata
    entry['mask_xyz']['radius']=input_root[scan_entry]['mask_xyz']['radius'].nxdata
    entry['mask_xyz']['H']=np.zeros(entry['mask_xyz']['x'].nxdata.shape[0])
    entry['mask_xyz']['K']=np.zeros(entry['mask_xyz']['x'].nxdata.shape[0])
    entry['mask_xyz']['L']=np.zeros(entry['mask_xyz']['x'].nxdata.shape[0])
    entry['mask_xyz']['pixel_count']=np.zeros(entry['mask_xyz']['x'].nxdata.shape[0])
    fx_reduce.write_mask(fx_reduce.read_peaks('mask_xyz'))
    fx_reduce.link_mask()
    input_root[scan_entry]['nxprepare_mask']=NXprocess()

    scan_entry='f3'
    fx_reduce=NXReduce(input_root[scan_entry])
    entry=fx_reduce.mask_root['entry']
    entry['mask_xyz']=NXcollection()
    entry['mask_xyz']['x']=input_root[scan_entry]['mask_xyz']['x'].nxdata
    entry['mask_xyz']['y']=input_root[scan_entry]['mask_xyz']['y'].nxdata
    entry['mask_xyz']['z']=input_root[scan_entry]['mask_xyz']['z'].nxdata
    entry['mask_xyz']['radius']=input_root[scan_entry]['mask_xyz']['radius'].nxdata
    entry['mask_xyz']['H']=np.zeros(entry['mask_xyz']['x'].nxdata.shape[0])
    entry['mask_xyz']['K']=np.zeros(entry['mask_xyz']['x'].nxdata.shape[0])
    entry['mask_xyz']['L']=np.zeros(entry['mask_xyz']['x'].nxdata.shape[0])
    entry['mask_xyz']['pixel_count']=np.zeros(entry['mask_xyz']['x'].nxdata.shape[0])
    fx_reduce.write_mask(fx_reduce.read_peaks('mask_xyz'))
    fx_reduce.link_mask()
    input_root[scan_entry]['nxprepare_mask']=NXprocess()

def skip_extras(input_root):
    scan_entry='f1'
    fx_reduce=NXReduce(input_root[scan_entry])
    entry=fx_reduce.mask_root['entry']
    if 'peaks_inferred' in entry:
        pixels=entry['peaks_inferred']['pixel_count'].nxdata
        pixels[pixels==0.5]=-1
        entry['peaks_inferred']['pixel_count'].nxdata=pixels

    scan_entry='f2'
    fx_reduce=NXReduce(input_root[scan_entry])
    entry=fx_reduce.mask_root['entry']
    if 'peaks_inferred' in entry:
        pixels=entry['peaks_inferred']['pixel_count'].nxdata
        pixels[pixels==0.5]=-1
        entry['peaks_inferred']['pixel_count'].nxdata=pixels

    scan_entry='f3'
    fx_reduce=NXReduce(input_root[scan_entry])
    entry=fx_reduce.mask_root['entry']
    if 'peaks_inferred' in entry:
        pixels=entry['peaks_inferred']['pixel_count'].nxdata
        pixels[pixels==0.5]=-1
        entry['peaks_inferred']['pixel_count'].nxdata=pixels

def replace_extras(input_root):
    scan_entry='f1'
    fx_reduce=NXReduce(input_root[scan_entry])
    entry=fx_reduce.mask_root['entry']
    if 'peaks_inferred' in entry:
        pixels=entry['peaks_inferred']['pixel_count'].nxdata
        pixels[pixels==0.5]=-1
        entry['peaks_inferred']['pixel_count'].nxdata=pixels

    scan_entry='f2'
    fx_reduce=NXReduce(input_root[scan_entry])
    entry=fx_reduce.mask_root['entry']
    if 'peaks_inferred' in entry:
        pixels=entry['peaks_inferred']['pixel_count'].nxdata
        pixels[pixels==0.5]=-1
        entry['peaks_inferred']['pixel_count'].nxdata=pixels

    scan_entry='f3'
    fx_reduce=NXReduce(input_root[scan_entry])
    entry=fx_reduce.mask_root['entry']
    if 'peaks_inferred' in entry:
        pixels=entry['peaks_inferred']['pixel_count'].nxdata
        pixels[pixels==0.5]=-1
        entry['peaks_inferred']['pixel_count'].nxdata=pixels

def use_existing_mask(input_root):
    scan_entry='f1'
    fx_reduce=NXReduce(input_root[scan_entry])
    entry=fx_reduce.mask_root['entry']
    if 'mask_xyz' in entry:
        del entry['mask_xyz']
    entry['mask_xyz']=NXcollection()
    entry['mask_xyz']['x']=np.zeros(0)
    entry['mask_xyz']['y']=np.zeros(0)
    entry['mask_xyz']['z']=np.zeros(0)
    entry['mask_xyz']['radius']=np.zeros(0)
    entry['mask_xyz']['H']=np.zeros(entry['mask_xyz']['x'].nxdata.shape[0])
    entry['mask_xyz']['K']=np.zeros(entry['mask_xyz']['x'].nxdata.shape[0])
    entry['mask_xyz']['L']=np.zeros(entry['mask_xyz']['x'].nxdata.shape[0])
    entry['mask_xyz']['pixel_count']=np.zeros(entry['mask_xyz']['x'].nxdata.shape[0])

    scan_entry='f2'
    fx_reduce=NXReduce(input_root[scan_entry])
    entry=fx_reduce.mask_root['entry']
    if 'mask_xyz' in entry:
        del entry['mask_xyz']
    entry['mask_xyz']=NXcollection()
    entry['mask_xyz']['x']=np.zeros(0)
    entry['mask_xyz']['y']=np.zeros(0)
    entry['mask_xyz']['z']=np.zeros(0)
    entry['mask_xyz']['radius']=np.zeros(0)
    entry['mask_xyz']['H']=np.zeros(entry['mask_xyz']['x'].nxdata.shape[0])
    entry['mask_xyz']['K']=np.zeros(entry['mask_xyz']['x'].nxdata.shape[0])
    entry['mask_xyz']['L']=np.zeros(entry['mask_xyz']['x'].nxdata.shape[0])
    entry['mask_xyz']['pixel_count']=np.zeros(entry['mask_xyz']['x'].nxdata.shape[0])

    scan_entry='f3'
    fx_reduce=NXReduce(input_root[scan_entry])
    entry=fx_reduce.mask_root['entry']
    if 'mask_xyz' in entry:
        del entry['mask_xyz']
    entry['mask_xyz']=NXcollection()
    entry['mask_xyz']['x']=np.zeros(0)
    entry['mask_xyz']['y']=np.zeros(0)
    entry['mask_xyz']['z']=np.zeros(0)
    entry['mask_xyz']['radius']=np.zeros(0)
    entry['mask_xyz']['H']=np.zeros(entry['mask_xyz']['x'].nxdata.shape[0])
    entry['mask_xyz']['K']=np.zeros(entry['mask_xyz']['x'].nxdata.shape[0])
    entry['mask_xyz']['L']=np.zeros(entry['mask_xyz']['x'].nxdata.shape[0])
    entry['mask_xyz']['pixel_count']=np.zeros(entry['mask_xyz']['x'].nxdata.shape[0])

def change_mask_radius(input_root,delta_r,entries=['f1','f2','f3']):
    if 'f1' in entries:
        fx_reduce=NXReduce(input_root['f1'])
        entry=fx_reduce.mask_root['entry']
        if 'old_mask_xyz' not in fx_reduce.mask_root['entry']:
            entry['old_mask_xyz']=entry['mask_xyz']
        radii=entry['mask_xyz']['radius']+delta_r
        radii[radii<0]=0
        entry['mask_xyz']['radius']=radii
        if 'mask' in entry:
            del entry['mask']
        fx_reduce.write_mask(fx_reduce.read_peaks('mask_xyz'))
        if 'mask_xyz_extras' in fx_reduce.mask_root['entry']:
            fx_reduce.write_mask(fx_reduce.read_peaks('mask_xyz_extras'))
        fx_reduce.write_mask(fx_reduce.read_peaks('mask_xyz_edges'))
    if 'f2' in entries:
        fx_reduce=NXReduce(input_root['f2'])
        entry=fx_reduce.mask_root['entry']
        if 'old_mask_xyz' not in fx_reduce.mask_root['entry']:
            entry['old_mask_xyz']=entry['mask_xyz']
        radii=entry['mask_xyz']['radius']+delta_r
        radii[radii<0]=0
        entry['mask_xyz']['radius']=radii
        if 'mask' in entry:
            del entry['mask']
        fx_reduce.write_mask(fx_reduce.read_peaks('mask_xyz'))
        if 'mask_xyz_extras' in fx_reduce.mask_root['entry']:
            fx_reduce.write_mask(fx_reduce.read_peaks('mask_xyz_extras'))
        fx_reduce.write_mask(fx_reduce.read_peaks('mask_xyz_edges'))
    if 'f3' in entries:
        fx_reduce=NXReduce(input_root['f3'])
        entry=fx_reduce.mask_root['entry']
        if 'old_mask_xyz' not in fx_reduce.mask_root['entry']:
            entry['old_mask_xyz']=entry['mask_xyz']
        radii=entry['mask_xyz']['radius']+delta_r
        radii[radii<0]=0
        entry['mask_xyz']['radius']=radii
        if 'mask' in entry:
            del entry['mask']
        fx_reduce.write_mask(fx_reduce.read_peaks('mask_xyz'))
        if 'mask_xyz_extras' in fx_reduce.mask_root['entry']:
            fx_reduce.write_mask(fx_reduce.read_peaks('mask_xyz_extras'))
        fx_reduce.write_mask(fx_reduce.read_peaks('mask_xyz_edges'))

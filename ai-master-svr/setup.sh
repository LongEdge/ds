#---------鍙傛暟閰嶇疆鍖?------------
#閮ㄧ讲鍩烘湰淇℃伅
PROJ_NAME='svr' #涓哄摢涓」鐩儴缃?MICROSVR_NAME='master4'
# 寰湇鍔＄鐞嗘湇鍔＄殑淇℃伅
# 鏈湇鍔＄殑淇℃伅
MICROSVR_LOCAL_OUTURL='http://<PRIVATE_HOST>' #docker澶栭儴璁块棶鐨勫湴鍧€锛堝闃块噷浜戠殑澶栫綉ip涔熼渶瑕佹墜鍔ㄦ寚瀹氾級
MICROSVR_LOCAL_OUTPORT=6064  #docker瀵瑰鏄犲皠绔彛
# 鏈湇鍔＄殑鏂囦欢鍚嶇О淇℃伅


#---------鍏ㄥ眬鍙橀噺鍖?---------------
CURRENT_DIR=$(cd $(dirname $0); pwd) # setup.sh褰撳墠鐨勭洰褰?#CURRENT_DIR=$(cd $(dirname $0); pwd) # setup.sh褰撳墠鐨勭洰褰?##
# docker鍚嶇О
DOCKER_IMAGE_NAME='dslowcode_'$PROJ_NAME        #涓€涓」鐩叡鐢ㄤ竴涓猟ocker image
DOCKER_CONTAINER_NAME=$PROJ_NAME'_'$MICROSVR_NAME

#del docker conters
#parameter:$1 container name
function DelDockerContainer
{
    #get container id by name
    container_id=$(docker ps -aqf "name=$1")
    echo $container_id
    if [ ! -z $container_id ]; then
        echo "is stoping container:"$1
        docker stop $container_id
        echo "is removing container:"$1
        docker rm $container_id
    else
        echo "container $1 not exist"
    fi
}

#del docker images
#parameter:$1 image name
function DelDockerImage
{
    image_id=$(docker inspect -f '{{.ID}}' $1)
    if [ ! -z $image_id ]; then
        echo "is removing container:"$image_id
        docker rmi $image_id
    else
        echo "image $1 not exist"
    fi
}

# create docker image
# parameter:$1 image name
function CreateDockerImage
{
    docker build -t $1 $CURRENT_DIR
    echo "create docker image $1 successful"
}

# create docker container
# parameter: $1 container name
# parameter: $2 port
function CreateDockerContainer
{
    # create docker container
    docker run --name $2 -ti -d  -p $3:6060  $1 
    
    container_id=$(docker inspect --format="{{.Id}}" $1)
    echo "sudo docker start  "$container_id 
}

function copyfile2docker
{
    container_id=$(docker inspect --format="{{.Id}}" $1)
    echo "docker cp $CURRENT_DIR/. $1":/app""
    docker cp $CURRENT_DIR/. $1":/app"

    docker restart $container_id
    echo "docker container("$1") is running ..."
}

#Auto depoly cskin svr dockers
function AutoDepolyDocker
{   
    echo $1
    if [ "$1" == "restart" ]
    then
        docker restart $DOCKER_CONTAINER_NAME
    elif [ "$1" == "start" ]
    then
        docker start $DOCKER_CONTAINER_NAME
    elif [ "$1" == "stop" ]
    then
        docker stop $DOCKER_CONTAINER_NAME
    elif [ "$1" == "recreate_image" ]
    then
        #鍒犻櫎docker image
        echo "del image:"$DOCKER_IMAGE_NAME
        DelDockerImage $DOCKER_IMAGE_NAME
        # Create docker image 
        echo "create image:"$DOCKER_IMAGE_NAME
        CreateDockerImage $DOCKER_IMAGE_NAME
    elif [ "$1" == "del_image" ]
    then
        #鍒犻櫎docker image
        echo "del image:"$DOCKER_IMAGE_NAME
        DelDockerImage $DOCKER_IMAGE_NAME
    elif [ "$1" == "recreate_container" ]
    then
        #鍒犻櫎docker container
        echo "del contaier:"$DOCKER_CONTAINER_NAME
        DelDockerContainer $DOCKER_CONTAINER_NAME  
        # create docker container
        echo "create container"$DOCKER_CONTAINER_NAME
        CreateDockerContainer $DOCKER_IMAGE_NAME $DOCKER_CONTAINER_NAME $MICROSVR_LOCAL_OUTPORT
        echo "copy the lastest file and restart container:"$DOCKER_CONTAINER_NAME
        copyfile2docker $DOCKER_CONTAINER_NAME
        # docker logs -f --tail=100 $DOCKER_CONTAINER_NAME
    elif [ "$1" == "del_container" ]
    then
        echo "del container"
        #鍒犻櫎docker container
        echo "del contaier:"$DOCKER_CONTAINER_NAME
        DelDockerContainer $DOCKER_CONTAINER_NAME  
    elif [ "$1" == "copyfiles" ]
    then
        echo "copy the lastest file and restart container:"$DOCKER_CONTAINER_NAME
        copyfile2docker $DOCKER_CONTAINER_NAME
        # docker logs -f --tail=100 $DOCKER_CONTAINER_NAME
    elif [ "$1" == "logs" ]
    then
        docker logs -f --tail=100 $DOCKER_CONTAINER_NAME
    else
        echo "璇疯緭鍏ュ涓嬫牸寮忕殑鍛戒护"
        echo "./setup.sh recreate_image             #鐢熸垚/閲嶆柊鐢熸垚 image (杩愯璇ュ懡浠や箣鍓嶏紝纭繚鐩稿叧container宸茬粡鍒犻櫎)"
        echo "./setup.sh del_image                  #鍒犻櫎 image (杩愯璇ュ懡浠や箣鍓嶏紝纭繚鐩稿叧container宸茬粡鍒犻櫎)"
        echo "./setup.sh recreate_container         #鐢熸垚/閲嶆柊鐢熸垚 container(鍦ㄥ凡缁忕敓鎴恑mage鐨勫墠鎻愪笅锛屼粠褰撳墠浠ｇ爜鍗曠嫭鐢熸垚鍙︿竴涓猚ontainer)"
        echo "./setup.sh del_container              #鍒犻櫎 container"
        echo "./setup.sh restart                    #閲嶅惎 container"
        echo "./setup.sh start                      #鍚姩 container"
        echo "./setup.sh stop                       #鍋滄 container"
        echo "./setup.sh copyfiles                  #鎷疯礉鏂囦欢鍒癱ontainer骞堕噸鍚?"
        echo "./setup.sh logs                       #鏌ョ湅璇ontaier鐨勮繍琛屾棩蹇?
        echo "--娴忚鍣ㄨ緭鍏?http://<PRIVATE_HOST>:"$MICROSVR_LOCAL_OUTPORT"/apidocs 鏌ョ湅鏈嶅姟鐨刟pi鎺ュ彛浣跨敤璇存槑"
    fi
}
AutoDepolyDocker $1 


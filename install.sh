#!/usr/bin/env bash
GREEN='\033[0;32m'
BLUE='\033[0;34m'
WHITE='\033[0;37m'
RED='\033[0;31m'
NC='\033[0m'
PACKAGE="pyro_support"
PACKAGE_NAME="${BLUE}${PACKAGE}${NC}"
INSTALLER_NAME="${WHITE}${PACKAGE} Installer: ${NC}"

INSTALL_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
INSTALL_FILES="${INSTALL_DIR}/install_files_${PACKAGE}.txt"
INSTALL_LOG="${INSTALL_DIR}/install_log_${PACKAGE}.log"

function checkVirutalEnv {
    if [[ ${VIRTUAL_ENV} == "" ]]; then
        echo -e "${RED}WARNING:${NC} Installing outside a Virtual Environment"
        echo "Proceed with installation? y/n"
        read CONTINUE
        if [[ ${CONTINUE} == "n" ]]; then
            exit 0
        fi
    else
        echo -e "${INSTALLER_NAME} Using Virtual Environment: ${BLUE}${VIRTUAL_ENV}${NC}"
    fi
}

if [[ $# -eq 0 ]]; then
    echo "Specify whether you're trying to install or uninstall"
    echo "-i for install"
    echo "-u for uninstall"
    echo "If you didn't install with this script, then it won't be able to uninstall"
else
    ARG=$1
fi

if [[ ${ARG} == "-i" ]]; then
    checkVirutalEnv
    echo -ne "${INSTALLER_NAME} Running setup.py..."
    cd ${INSTALL_DIR}
    python setup.py install --record ${INSTALL_FILES} >>${INSTALL_LOG} 2>&1
    EXITCODE=$?
    if [[ ${EXITCODE} -eq 0 ]]; then
        echo -e "\r${INSTALLER_NAME} Running setup.py... ${GREEN}Done!${NC}"
        exit 0
    else
        echo -e "\r${INSTALLER_NAME} Running setup.py... ${RED}Failed.${NC}"
        exit 1
    fi
elif [[ ${ARG} == "-u" ]]; then
    echo -e "${INSTALLER_NAME} Attempting to uninstall ${PACKAGE_NAME}"
    if [[ -e ${INSTALL_FILES} ]]; then
        echo -ne "${INSTALLER_NAME} Finding egg files and deleting... "
        xargs rm <${INSTALL_FILES} 2> /dev/null
        EXITCODE=$?
        if [[ ${EXITCODE} -eq 0 ]]; then
            echo -e "\r${INSTALLER_NAME} Finding egg files and deleting... ${GREEN}Done!${NC}"
        else
            echo -e "\r${INSTALLER_NAME} Finding egg files and deleting... ${RED}Files already deleted.${NC}"
        fi
    else
        echo -e "${INSTALLER_NAME} Couldn't find the files to remove"
        echo -e "${INSTALLER_NAME} Did you install with this script, or did you run uninstall without installing first?"
    fi
fi

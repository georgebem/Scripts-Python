# -*- coding: UTF-8 -*-

import logging.handlers
import traceback
import sys
import arcgis
import csv
import arrow
from arcgis.gis import *
from arcgis.geocoding import geocode
# utiliza o python 3.6
#link do projeto no workforce do portal: https://noteimg415.img.local/arcgis/apps/workforce/#/projects/98c2751eb4e94b0ea29afd9dd4593eef/dispatch/assignments
url = 'https://noteimg415.img.local/arcgis' #url do portal
usuario = 'portal' #usuario do portal com privilegio de Dispatcher
senha = '*******' #senha do Dispatcher
projetoId = '98c2751eb4e94b0ea29afd9dd4593eef' #id do projeto no workforce, ver link acima
arquivoLog = 'D:\TEMP\log.txt' #arquivo de log. A pasta deve estar criada antes de rodar o programa. O arquivo é recriado a cada vez que o script roda
arquivoCSV = 'D:\DADOS\SCRIPTS_PHYTON\WorkForce\dados.csv' #arquivo de dados, separado por ponto-e-virgufa, no formato abaixo

"""
Rua Itororo,555, Sao Jose dos Campos,SP, Brasil;Ordem de Servico 01:Descricao da tarefa;0;1;0;100001;2;isto eh uma nota aaa
Av. Andromeda, 1000, Sao Jose dos Campos, SP, Brasil;Ordem de Servico 03:Descricao da tarefa;2;1;0;100003;48;isto eh uma nota ccc
Av. Dep. Benedito Matarazzo, 9521, Sao Jose dos Campos, SP, Brasil;Ordem de Servico 03:Descricao da tarefa;3;1;0;100004;72;isto eh uma nota ddd
Av. Heitor Villa Lobos, 1319, Sao Jose dos Campos, SP, Brasil;Pesquisa:Descricao da tarefa;4;2;0;100005;2;isto eh uma nota eee

[0] primeira coluna: Endereco a ser geocodificado e tb salvo no campo location
( type: esriFieldTypeString , alias: Location , length: 255 , nullable: true , editable: true )

[1] segunda coluna: Descricao da tarefa
( type: esriFieldTypeString , alias: Description , length: 4000 , nullable: true , editable: true )

[2] terceria coluna: Prioridade
( type: esriFieldTypeInteger , alias: Priority , nullable: true , editable: true , Coded Values: [0: None] , [1: Low] , [2: Medium] [3:High] [4:Critical] )

[3] quarta coluna: Tipo do Assignement, conforme foi configurado no projeto do workforce
( type: esriFieldTypeInteger , alias: Assignment Type , nullable: true , editable: true , Coded Values: [1: Ordem de Serviço] , [2: Pesquisa] )

[4] quinta coluna: status - nos testes, eu sempre coloquei como 0, para ser associado posteriormente pela tela do workforce
 ( type: esriFieldTypeInteger , alias: Status , nullable: true , editable: true , Coded Values: [0: Unassigned] , [1: Assigned] , [2: In Progress] , ...4 more... )

[5] sexta coluna: workerid id do sistema interno
( type: esriFieldTypeInteger , alias: WorkerID , nullable: true , editable: true )

[6] setima coluna: shift em horas, utilizado para calcular o duedate. Exeplo: data e hora atual + 12 horas
duedate ( type: esriFieldTypeDate , alias: Due Date , length: 29 , nullable: true , editable: true )

[7] oitava coluna: notas
( type: esriFieldTypeString , alias: Notes , length: 4000 , nullable: true , editable: true )
"""

def initialize_logging(log_file):
    #caso exista, apaga o arquivo de log anterior
    os.remove(arquivoLog)
    # inicializa o log
    formatter = logging.Formatter("[%(asctime)s] [%(funcName)30s()] [%(name)10.10s] [%(levelname)8s] %(message)s")
    logger = logging.getLogger()
    # Set the root logger logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    logger.setLevel(logging.INFO)
    # Create a handler to print to the console
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)
    sh.setLevel(logging.INFO)
    # Create a handler to log to the specified file
    rh = logging.handlers.RotatingFileHandler(arquivoLog, mode='a', maxBytes=10485760)
    rh.setFormatter(formatter)
    rh.setLevel(logging.INFO)
    # Add the handlers to the root logger
    logger.addHandler(sh)
    logger.addHandler(rh)
    return logger
#
logger = initialize_logging(arquivoLog) #D:\TEMP\log.txt



def get_assignments_from_csv():
    assignments_to_add = []
    assignments_in_csv = []
    dev_gis = GIS()
    csvFile = os.path.abspath(arquivoCSV)
    logger.info("Lendo CSV {}...".format(csvFile))

    with open(csvFile, 'r') as file:
        reader = csv.reader(file, delimiter=';')# o delimitador eh ponto-e-virgula
        for row in reader:
            assignments_in_csv.append(row)

    for assignment in assignments_in_csv:
        logger.info(assignment)#loga os campos
        #!!! ATENCAO!!!
        #o Geocode abaixo utiliza o geocode gratuito, ou seja, não consome créditos e faz chamadas individuais
        #se fizer muitos geocodes, pode colocar o ip do solicitador na lista negra da esri
        #para uso em producao, deve ser alterado para utilizar uma conta agol ou o geocode com locators locais, publicados no Enterprise
        geocode_result = geocode(address=assignment[0], as_featureset=True)#Geocode
        if len(geocode_result.features) > 0: #se o geocode encontrou pelo menos uma equivalencia, pega a primeira, se nao encontrou, passa para a proxima linha do CSV
            geometry = geocode_result.features[0].geometry#teoricamenteo o lat long com maior assertividade
            logger.info(geometry)#registra no,log
            # Cria os outros atributos
            # calcula a duedate em formato de milissegundos utc, adicionados do shift em horas da coluna [6]
            horas = int(assignment[6])
            prazo =(float(arrow.utcnow().shift(hours=horas).format('X')))*1000
            #os atributos do dicionario devem ser criados conforme os fields do hosted service http://noteimg415.img.local/server/rest/services/Hosted/assignments_fadecb6e28be45f9b12048336a5a070b/FeatureServer/0
            attributes = dict(location=assignment[0],
                              description=assignment[1],
                              priority=assignment[2],
                              assignmenttype=assignment[3],
                              status=assignment[4],
                              workorderid=assignment[5],
                              duedate=prazo,
                              notes=assignment[7],
                              assignmentread=None)
            #adiciona a geometria e os atributos a um novo assignment
            new_assignment = arcgis.features.Feature(geometry=geometry, attributes=attributes)
            assignment_dict = (dict(assignment=new_assignment))
            logger.info(assignment_dict)
            assignments_to_add.append(assignment_dict)
    #por fim, retorno todos os assignments que foram possiveis de geocodificar e preencher os atributos
    return assignments_to_add


def main():
    try:
        logger.info("Autenticando e obtendo dados do projeto no Workforce...")
        gis = arcgis.gis.GIS(url, usuario, senha)
        content_manager = arcgis.gis.ContentManager(gis)
        workforce_project = content_manager.get(projetoId)
        workforce_project_data = workforce_project.get_data()
        assignment_fl = arcgis.features.FeatureLayer(workforce_project_data["assignments"]["url"], gis)
        dispatcher_fl = arcgis.features.FeatureLayer(workforce_project_data["dispatchers"]["url"], gis)
        worker_fl = arcgis.features.FeatureLayer(workforce_project_data["workers"]["url"], gis)

        # verifica se o usuario eh um Dispatcher
        id = None
        dispatchers = dispatcher_fl.query(where="userId='{}'".format(usuario))
        if dispatchers.features:
            id = dispatchers.features[0].attributes['objectid']
        else:
            logger.critical("{} nao eh um dispatcher".format(usuario))
            return
        #obter os assignments no CSV
        assignments = get_assignments_from_csv()
        # Define o dispatcherId en todos os assignments
        for assignment in [x["assignment"] for x in assignments]:
            if "dispatcherid" not in assignment.attributes:
                assignment.attributes["dispatcherid"] = id

        # set worker ids
        # esta parte nao esta funcionando nesta versao, pois o atributo name nao esta no arquivo csv
        for assignment in assignments:
            if "name" in assignment and assignment["name"]:
                workers = worker_fl.query(where="name='{}'".format(assignment["name"]))
                if workers.features:
                    assignment["assignment"].attributes["status"] = 1  # assigned
                    assignment["assignment"].attributes["assigneddate"] = arrow.now().to('utc').strftime(
                        "%m/%d/%Y %H:%M:%S")
                else:
                    logger.critical("{} nao eh um worker".format(assignment["name"]))
                    return

        # Add the assignments
        logger.info("Adicionando Assignments...")
        response = assignment_fl.edit_features(adds=arcgis.features.FeatureSet([x["assignment"] for x in assignments]))
        logger.info(response)
        # Assign the returned object ids to the assignment dictionary object
        for i in range(len(response["addResults"])):
            assignments[i]["assignment"].attributes["objectid"] = response["addResults"][i]["objectId"]
        logger.info("Completed")

    except Exception as e:
        logging.getLogger().critical("Exception detected, script exiting")
        logging.getLogger().critical(e)
        logging.getLogger().critical(traceback.format_exc().replace("\n", " | "))

if __name__ == "__main__":
    main()
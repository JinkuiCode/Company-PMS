1 统一认证

         1.1术语约定


统一认证服务部署目录(weaversso目录)：SSO_DIR

OA部署目录(ecology目录)：EC_DIR

中间件部署目录(resin目录)：RESIN_DIR

CLASS编译目录(classbean目录)：CLASS_DIR

 

         1.2配置统一认证服务


在web中间件(resin,tomcat,weblogic…)里配置好统一认证服务，请务必配置好。下面以resin3，resin4为例，描述配置统一认证服务。

Resin3版本的配置：在RESIN_DIR\conf\resin.conf的host节点增加以下配置，请配置在 <web-app id="/"></web-app>的后面，如下所示：

<web-app id="/sso" root-directory="d:\weaver\weaversso">

    <servlet-mapping url-pattern='/weaver/*' servlet-name='invoker'/>

</web-app>

 

Resin4版本的配置： 在RESIN_DIR\conf\resin.xml的host节点增加以下配置，请配置在 <web-app id="/"></web-app>的后面，如下所示：

<web-app id="/sso" root-directory="d:\weaver\weaversso">

    <servlet-mapping url-pattern='/weaver/*' servlet-name='invoker'/>

</web-app>

 

注意：统一认证服务的部署目录，请根据实际情况填写。

         1.3配置统一认证服务数据源


找到SSO_DIR/WEB-INF/spring-configuration/propertyFileConfigurer.xml，请根据EC_DIR部署情况，务必配置好如下红色字体的路径，如下：

<bean id="propertyPlaceholderConfigurer" class="org.springframework.beans.factory.config.PropertyPlaceholderConfigurer">
   <property name="locations" >
     <list>
       <value>/WEB-INF/cas.properties</value>
       <value>file:F:/workspaces/e9/web/WEB-INF/prop/weaver.properties</value>
     </list>
   </property>
</bean>

 

 

注意：红色的路径地址需要根据实际情况指定修改,注意windows系统的服务器需要盘符,如：

file:D:/WEAVER/ecology/WEB-INF/prop/weaver.properties

linux系统则不需要盘符,如：

file:/usr/WEAVER/ecology/WEB-INF/prop/weaver.properties

 

         1.4配置OA访问地址


启用统一认证中心之前，请务必配置好OA访问地址。

         1.5测试统一认证服务


复制统一认证地址登录地址，在浏览器访问该地址，如果能正确跳转到登录页面，即为部署成功。不然就是没部署好，继续检查上面的步骤是否都做对了。

         1.6保存配置


上面一步部署成功后，可点击启用并保存，将提示服务会自动重启，配置会写入EC_DIR/WEB-INF/web.xml，等待系统自动重启，或手动重启系统，访问OA，跳转到认证页面，浏览器地址栏里URL刷出service参数，即表示成功，至此整个统一认证服务的基本配置结束。

 

2 统一用户

         2.1 统一用户webservice接口


请在weaver\ecology\classbean\META-INF\xfire\services.xml里面检查是否有以下代码，没有则添加：

<service>

    <name>HrmService</name>

    <namespace>http://localhost/services/HrmService</namespace>

    <serviceClass>weaver.hrm.webservice.HrmService</serviceClass>

    <implementationClass>weaver.hrm.webservice.HrmServiceImpl</implementationClass>

    <serviceFactory>org.codehaus.xfire.annotations.AnnotationServiceFactory</serviceFactory>

  </service>

 

         2.2 人员映射接口（选配）


如果第三方系统需要通过接口同步数据才配置，接入系统根据人员映射接口规范，将人员数据的映射关系推送给ecology。

1、      WebService接口
请在weaver\ecology\classbean\META-INF\xfire\services.xml文件中添加如下配置：

<service>

<name>AddUserInterface</name>

<namespace>weaversso.weaver.com.cn</namespace>

<serviceClass>weaver.weaversso.AddUserInterface</serviceClass>

<implementationClass>weaver.weaversso.AddUserInterfaceImpl</implementationClass>

</service>

 

接口地址
http://OA地址/services/AddUserInterface?wsdl

 

2、      REST接口
请在ecology\WEB-INF\web.xml 文件中添加如下配置：

<servlet>

<servlet-name>AddUserServlet</servlet-name>

<servlet-class>weaver.weaversso.AddUserServlet</servlet-class>

</servlet>

<servlet-mapping>

<servlet-name>AddUserServlet</servlet-name>

<url-pattern>/data/pushUserMap</url-pattern>

</servlet-mapping>

 

接口地址
http://OA地址:port/data/pushUserMap

 

3 第三方异构系统单点登录ecology (TOKEN方式)

         3.1 配置


注意：如果只用该方式实现第三方异构系统单点登录Ecology，则不需要配置第一节的统一认证服务，请直接在功能页面“统一认证中心”基本信息配置界面启用TOKEN方式，并在注册应用配置相关信息，无需额外配置。









1 统一认证

         1.1术语约定


统一认证服务部署目录(weaversso目录)：SSO_DIR

OA部署目录(ecology目录)：EC_DIR

中间件部署目录(resin目录)：RESIN_DIR

CLASS编译目录(classbean目录)：CLASS_DIR

 

         1.2配置统一认证服务


在web中间件(resin,tomcat,weblogic…)里配置好统一认证服务，请务必配置好。下面以resin3，resin4为例，描述配置统一认证服务。

Resin3版本的配置：在RESIN_DIR\conf\resin.conf的host节点增加以下配置，请配置在 <web-app id="/"></web-app>的后面，如下所示：

<web-app id="/sso" root-directory="d:\weaver\weaversso">

    <servlet-mapping url-pattern='/weaver/*' servlet-name='invoker'/>

</web-app>

 

Resin4版本的配置： 在RESIN_DIR\conf\resin.xml的host节点增加以下配置，请配置在 <web-app id="/"></web-app>的后面，如下所示：

<web-app id="/sso" root-directory="d:\weaver\weaversso">

    <servlet-mapping url-pattern='/weaver/*' servlet-name='invoker'/>

</web-app>

 

注意：统一认证服务的部署目录，请根据实际情况填写。

         1.3配置统一认证服务数据源


找到SSO_DIR/WEB-INF/spring-configuration/propertyFileConfigurer.xml，请根据EC_DIR部署情况，务必配置好如下红色字体的路径，如下：

<bean id="propertyPlaceholderConfigurer" class="org.springframework.beans.factory.config.PropertyPlaceholderConfigurer">
   <property name="locations" >
     <list>
       <value>/WEB-INF/cas.properties</value>
       <value>file:F:/workspaces/e9/web/WEB-INF/prop/weaver.properties</value>
     </list>
   </property>
</bean>

 

 

注意：红色的路径地址需要根据实际情况指定修改,注意windows系统的服务器需要盘符,如：

file:D:/WEAVER/ecology/WEB-INF/prop/weaver.properties

linux系统则不需要盘符,如：

file:/usr/WEAVER/ecology/WEB-INF/prop/weaver.properties

 

         1.4配置OA访问地址


启用统一认证中心之前，请务必配置好OA访问地址。

         1.5测试统一认证服务


复制统一认证地址登录地址，在浏览器访问该地址，如果能正确跳转到登录页面，即为部署成功。不然就是没部署好，继续检查上面的步骤是否都做对了。

         1.6保存配置


上面一步部署成功后，可点击启用并保存，将提示服务会自动重启，配置会写入EC_DIR/WEB-INF/web.xml，等待系统自动重启，或手动重启系统，访问OA，跳转到认证页面，浏览器地址栏里URL刷出service参数，即表示成功，至此整个统一认证服务的基本配置结束。

 

2 统一用户

         2.1 统一用户webservice接口


请在weaver\ecology\classbean\META-INF\xfire\services.xml里面检查是否有以下代码，没有则添加：

<service>

    <name>HrmService</name>

    <namespace>http://localhost/services/HrmService</namespace>

    <serviceClass>weaver.hrm.webservice.HrmService</serviceClass>

    <implementationClass>weaver.hrm.webservice.HrmServiceImpl</implementationClass>

    <serviceFactory>org.codehaus.xfire.annotations.AnnotationServiceFactory</serviceFactory>

  </service>

 

         2.2 人员映射接口（选配）


如果第三方系统需要通过接口同步数据才配置，接入系统根据人员映射接口规范，将人员数据的映射关系推送给ecology。

1、      WebService接口
请在weaver\ecology\classbean\META-INF\xfire\services.xml文件中添加如下配置：

<service>

<name>AddUserInterface</name>

<namespace>weaversso.weaver.com.cn</namespace>

<serviceClass>weaver.weaversso.AddUserInterface</serviceClass>

<implementationClass>weaver.weaversso.AddUserInterfaceImpl</implementationClass>

</service>

 

接口地址
http://OA地址/services/AddUserInterface?wsdl

 

2、      REST接口
请在ecology\WEB-INF\web.xml 文件中添加如下配置：

<servlet>

<servlet-name>AddUserServlet</servlet-name>

<servlet-class>weaver.weaversso.AddUserServlet</servlet-class>

</servlet>

<servlet-mapping>

<servlet-name>AddUserServlet</servlet-name>

<url-pattern>/data/pushUserMap</url-pattern>

</servlet-mapping>

 

接口地址
http://OA地址:port/data/pushUserMap

 

3 第三方异构系统单点登录ecology (TOKEN方式)

         3.1 配置


注意：如果只用该方式实现第三方异构系统单点登录Ecology，则不需要配置第一节的统一认证服务，请直接在功能页面“统一认证中心”基本信息配置界面启用TOKEN方式，并在注册应用配置相关信息，无需额外配置。